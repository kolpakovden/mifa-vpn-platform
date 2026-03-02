package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"golang.org/x/net/publicsuffix"
	"gopkg.in/yaml.v3"
)

type Config struct {
	InputLog    string `yaml:"input_log"`
	OutputJSONL string `yaml:"output_jsonl"`

	MetricsAddr string `yaml:"metrics_addr"`

	BrandsPath    string `yaml:"brands_path"`
	WatchlistPath string `yaml:"watchlist_path"`

	Geo struct {
		Enabled  bool   `yaml:"enabled"`
		Provider string `yaml:"provider"` // ipwhois
		BaseURL  string `yaml:"base_url"`
		Timeout  string `yaml:"timeout"`
		CacheTTL string `yaml:"cache_ttl"`
		MaxQPS   int    `yaml:"max_qps"`
	} `yaml:"geo"`

	Parser struct {
		Regex string `yaml:"regex"`
	} `yaml:"parser"`
}

type BrandsFile struct {
	Brands map[string][]string `yaml:"brands"`
}

type WatchlistFile struct {
	Rules []struct {
		Name     string `yaml:"name"`
		Severity string `yaml:"severity"`
		Match    struct {
			Domains []string `yaml:"domains"`
			Brands  []string `yaml:"brands"`
		} `yaml:"match"`
	} `yaml:"rules"`
	RateLimit struct {
		PerUser struct {
			Critical string `yaml:"critical"`
			Warn     string `yaml:"warn"`
		} `yaml:"per_user"`
	} `yaml:"rate_limit"`
}

type GeoInfo struct {
	Country string  `json:"country,omitempty"`
	Region  string  `json:"region,omitempty"`
	City    string  `json:"city,omitempty"`
	ISP     string  `json:"isp,omitempty"`
	ASNOrg  string  `json:"asn_org,omitempty"`
	ASN     int     `json:"asn,omitempty"`
	Lat     float64 `json:"lat,omitempty"`
	Lon     float64 `json:"lon,omitempty"`
}

type Event struct {
	TS      string `json:"ts"`
	User    string `json:"user"`
	SrcIP   string `json:"src_ip"`
	SrcPort int    `json:"src_port"`

	DstProto string `json:"dst_proto"`
	DstHost  string `json:"dst_host"`
	DstPort  int    `json:"dst_port"`

	Route string `json:"route"`

	Domain string `json:"domain"`
	Brand  string `json:"brand"`

	Geo GeoInfo `json:"geo"`

	WatchHit bool   `json:"watch_hit"`
	Severity string `json:"severity,omitempty"`
	Rule     string `json:"rule,omitempty"`
}

func loadYAML[T any](path string, out *T) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return yaml.Unmarshal(b, out)
}

func normalizeHostToDomain(host string) (string, bool) {
	h := strings.TrimSpace(strings.Trim(host, "[]"))
	// strip trailing dot
	h = strings.TrimSuffix(h, ".")
	if net.ParseIP(h) != nil {
		return "ip_literal", true
	}
	h = strings.ToLower(h)
	d, err := publicsuffix.EffectiveTLDPlusOne(h)
	if err != nil {
		return "other", false
	}
	return d, false
}

type BrandMapper struct {
	domainToBrand map[string]string
}

func newBrandMapper(path string) (*BrandMapper, error) {
	var bf BrandsFile
	if err := loadYAML(path, &bf); err != nil {
		return nil, err
	}
	m := make(map[string]string, 1024)
	for brand, domains := range bf.Brands {
		for _, d := range domains {
			d = strings.ToLower(strings.TrimSpace(d))
			if d == "" {
				continue
			}
			m[d] = brand
		}
	}
	return &BrandMapper{domainToBrand: m}, nil
}

func (bm *BrandMapper) brand(domain string) string {
	if b, ok := bm.domainToBrand[domain]; ok {
		return b
	}
	return "unknown"
}

type WatchRule struct {
	Name     string
	Severity string
	Domains  map[string]struct{}
	Brands   map[string]struct{}
}

type RateLimiter struct {
	mu           sync.Mutex
	nextAllowed  map[string]time.Time
	winCritical  time.Duration
	winWarn      time.Duration
}

func newRateLimiter(crit, warn time.Duration) *RateLimiter {
	return &RateLimiter{
		nextAllowed: make(map[string]time.Time),
		winCritical: crit,
		winWarn:     warn,
	}
}

func (rl *RateLimiter) allow(key, severity string, now time.Time) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	if t, ok := rl.nextAllowed[key]; ok && now.Before(t) {
		return false
	}
	win := rl.winWarn
	if severity == "critical" {
		win = rl.winCritical
	}
	rl.nextAllowed[key] = now.Add(win)
	return true
}

type Watchlist struct {
	rules []*WatchRule
	rl    *RateLimiter
}

func newWatchlist(path string) (*Watchlist, error) {
	var wf WatchlistFile
	if err := loadYAML(path, &wf); err != nil {
		return nil, err
	}
	crit, _ := time.ParseDuration(wf.RateLimit.PerUser.Critical)
	warn, _ := time.ParseDuration(wf.RateLimit.PerUser.Warn)
	if crit == 0 { crit = 5 * time.Minute }
	if warn == 0 { warn = 30 * time.Minute }

	wl := &Watchlist{rl: newRateLimiter(crit, warn)}

	for _, r := range wf.Rules {
		wr := &WatchRule{
			Name:     r.Name,
			Severity: strings.ToLower(strings.TrimSpace(r.Severity)),
			Domains:  map[string]struct{}{},
			Brands:   map[string]struct{}{},
		}
		for _, d := range r.Match.Domains {
			d = strings.ToLower(strings.TrimSpace(d))
			if d != "" {
				wr.Domains[d] = struct{}{}
			}
		}
		for _, b := range r.Match.Brands {
			b = strings.ToLower(strings.TrimSpace(b))
			if b != "" {
				wr.Brands[b] = struct{}{}
			}
		}
		if wr.Severity == "" {
			wr.Severity = "warn"
		}
		wl.rules = append(wl.rules, wr)
	}
	return wl, nil
}

func (wl *Watchlist) check(user, domain, brand string, now time.Time) (hit bool, severity, rule string) {
	for _, r := range wl.rules {
		_, domMatch := r.Domains[domain]
		_, brMatch := r.Brands[brand]
		if domMatch || brMatch {
			key := fmt.Sprintf("%s|%s|%s", user, r.Severity, r.Name)
			if wl.rl.allow(key, r.Severity, now) {
				return true, r.Severity, r.Name
			}
			return false, "", ""
		}
	}
	return false, "", ""
}

type geoCacheEntry struct {
	info   GeoInfo
	expiry time.Time
}

type GeoClient struct {
	enabled bool
	baseURL string
	timeout time.Duration
	ttl     time.Duration
	qps     int

	mu    sync.Mutex
	cache map[string]geoCacheEntry

	tokMu sync.Mutex
	toks  int
	last  time.Time
}

func newGeoClient(cfg Config) (*GeoClient, error) {
	g := &GeoClient{
		enabled: cfg.Geo.Enabled,
		baseURL: cfg.Geo.BaseURL,
		cache:   map[string]geoCacheEntry{},
		qps:     cfg.Geo.MaxQPS,
	}
	if g.qps <= 0 { g.qps = 1 }
	var err error
	g.timeout, err = time.ParseDuration(cfg.Geo.Timeout)
	if err != nil || g.timeout == 0 { g.timeout = 2 * time.Second }
	g.ttl, err = time.ParseDuration(cfg.Geo.CacheTTL)
	if err != nil || g.ttl == 0 { g.ttl = 24 * time.Hour }
	g.last = time.Now()
	g.toks = g.qps
	return g, nil
}

func (g *GeoClient) takeToken() {
	g.tokMu.Lock()
	defer g.tokMu.Unlock()
	now := time.Now()
	// refill each second
	if now.Sub(g.last) >= time.Second {
		g.toks = g.qps
		g.last = now
	}
	if g.toks > 0 {
		g.toks--
		return
	}
	// wait until next second
	sleep := time.Second - now.Sub(g.last)
	if sleep < 0 { sleep = time.Second }
	time.Sleep(sleep)
	g.toks = g.qps - 1
	g.last = time.Now()
}

func (g *GeoClient) lookup(ip string) GeoInfo {
	if !g.enabled {
		return GeoInfo{}
	}
	if net.ParseIP(ip) == nil {
		return GeoInfo{}
	}

	now := time.Now()
	g.mu.Lock()
	if e, ok := g.cache[ip]; ok && now.Before(e.expiry) {
		g.mu.Unlock()
		return e.info
	}
	g.mu.Unlock()

	g.takeToken()

	client := &http.Client{Timeout: g.timeout}
	url := strings.TrimSuffix(g.baseURL, "/") + "/" + ip
	resp, err := client.Get(url)
	if err != nil {
		return GeoInfo{}
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	// ipwho.is format
	var raw struct {
		Success   bool    `json:"success"`
		Country   string  `json:"country"`
		Region    string  `json:"region"`
		City      string  `json:"city"`
		Latitude  float64 `json:"latitude"`
		Longitude float64 `json:"longitude"`
		Connection struct {
			ASN  int    `json:"asn"`
			Org  string `json:"org"`
			ISP  string `json:"isp"`
		} `json:"connection"`
	}
	if err := json.Unmarshal(body, &raw); err != nil || !raw.Success {
		return GeoInfo{}
	}

	info := GeoInfo{
		Country: raw.Country,
		Region:  raw.Region,
		City:    raw.City,
		Lat:     raw.Latitude,
		Lon:     raw.Longitude,
		ASN:     raw.Connection.ASN,
		ASNOrg:  raw.Connection.Org,
		ISP:     raw.Connection.ISP,
	}

	g.mu.Lock()
	g.cache[ip] = geoCacheEntry{info: info, expiry: now.Add(g.ttl)}
	g.mu.Unlock()

	return info
}

// Prometheus metrics
var (
	userReq = prometheus.NewCounterVec(
		prometheus.CounterOpts{Name: "mifa_user_requests_total", Help: "Requests per user from access.log"},
		[]string{"user"},
	)
	userBrandReq = prometheus.NewCounterVec(
		prometheus.CounterOpts{Name: "mifa_user_brand_requests_total", Help: "Requests per user per brand"},
		[]string{"user", "brand"},
	)
	userLastSeen = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{Name: "mifa_user_last_seen_timestamp", Help: "Last seen unix timestamp per user"},
		[]string{"user"},
	)
	watchHits = prometheus.NewCounterVec(
		prometheus.CounterOpts{Name: "mifa_watchlist_hits_total", Help: "Watchlist hits"},
		[]string{"user", "severity", "rule"},
	)
)

func mustRegisterMetrics() {
	prometheus.MustRegister(userReq, userBrandReq, userLastSeen, watchHits)
}

type Parser struct {
	re *regexp.Regexp
}

func newParser(regex string) (*Parser, error) {
	re, err := regexp.Compile(regex)
	if err != nil {
		return nil, err
	}
	return &Parser{re: re}, nil
}

func (p *Parser) parse(line string) (Event, bool) {
	m := p.re.FindStringSubmatch(line)
	if m == nil {
		return Event{}, false
	}
	get := func(name string) string {
		i := p.re.SubexpIndex(name)
		if i <= 0 || i >= len(m) {
			return ""
		}
		return m[i]
	}

	srcPort, _ := strconv.Atoi(get("src_port"))
	dstPort, _ := strconv.Atoi(get("dst_port"))

	ev := Event{
		TS:      get("ts"),
		User:    get("email"),
		SrcIP:   get("src_ip"),
		SrcPort: srcPort,
		DstProto: get("dst_proto"),
		DstHost:  get("dst_host"),
		DstPort:  dstPort,
		Route:    get("route"),
	}
	return ev, true
}

// Tail with rotation support
// Polling tailer: reliable on any FS (no inotify). Reads new lines appended to file.
type Tailer struct {
	path string
	out  chan string
	stop chan struct{}
	wg   sync.WaitGroup
}

func newTailer(path string) *Tailer {
	return &Tailer{
		path: path,
		out:  make(chan string, 1000),
		stop: make(chan struct{}),
	}
}

func (t *Tailer) Lines() <-chan string { return t.out }

func (t *Tailer) Start() error {
	t.wg.Add(1)
	go func() {
		defer t.wg.Done()
		defer close(t.out)

		var f *os.File
		var r *bufio.Reader
		var lastInode uint64

		openAtEnd := func() error {
			if f != nil {
				_ = f.Close()
			}
			ff, err := os.Open(t.path)
			if err != nil {
				return err
			}
			// tail -F behavior: start at end
			if _, err := ff.Seek(0, io.SeekEnd); err != nil {
				_ = ff.Close()
				return err
			}
			st, _ := ff.Stat()
			if st != nil {
				if sys, ok := st.Sys().(*syscall.Stat_t); ok {
					lastInode = sys.Ino
				}
			}
			f = ff
			r = bufio.NewReader(f)
			return nil
		}

		// initial open
		for {
			if err := openAtEnd(); err != nil {
				log.Printf("tail open error: %v", err)
				select {
				case <-t.stop:
					return
				case <-time.After(1 * time.Second):
					continue
				}
			}
			break
		}

		for {
			select {
			case <-t.stop:
				_ = f.Close()
				return
			default:
			}

			// try read a line
			line, err := r.ReadString('\n')
			if err == nil {
				t.out <- strings.TrimRight(line, "\r\n")
				continue
			}
			if !errors.Is(err, io.EOF) {
				log.Printf("tail read error: %v", err)
			}

			// check rotation (inode change) or truncation
			st, statErr := os.Stat(t.path)
			if statErr == nil && st != nil {
				if sys, ok := st.Sys().(*syscall.Stat_t); ok {
					if sys.Ino != lastInode {
						_ = openAtEnd()
					}
				}
				// truncation
				if f != nil {
					if cur, _ := f.Seek(0, io.SeekCurrent); cur > st.Size() {
						_ = openAtEnd()
					}
				}
			}

			time.Sleep(200 * time.Millisecond)
		}
	}()
	return nil
}

func (t *Tailer) Stop() {
	close(t.stop)
	t.wg.Wait()
}


func ensureParent(path string) error {
	dir := filepath.Dir(path)
	return os.MkdirAll(dir, 0750)
}

func main() {
	cfgPath := "/etc/mifa/log-processor.yaml"
	if len(os.Args) > 1 {
		cfgPath = os.Args[1]
	}

	var cfg Config
	if err := loadYAML(cfgPath, &cfg); err != nil {
		log.Fatalf("load config: %v", err)
	}

	if cfg.MetricsAddr == "" {
		cfg.MetricsAddr = ":9105"
	}

	parser, err := newParser(cfg.Parser.Regex)
	if err != nil {
		log.Fatalf("bad regex: %v", err)
	}

	bm, err := newBrandMapper(cfg.BrandsPath)
	if err != nil {
		log.Fatalf("load brands: %v", err)
	}

	wl, err := newWatchlist(cfg.WatchlistPath)
	if err != nil {
		log.Fatalf("load watchlist: %v", err)
	}

	geo, _ := newGeoClient(cfg)

	if err := ensureParent(cfg.OutputJSONL); err != nil {
		log.Fatalf("ensure output dir: %v", err)
	}

	out, err := os.OpenFile(cfg.OutputJSONL, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0640)
	if err != nil {
		log.Fatalf("open output: %v", err)
	}
	defer out.Close()

	// Metrics HTTP
	mustRegisterMetrics()
	go func() {
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		log.Printf("metrics on %s", cfg.MetricsAddr)
		if err := http.ListenAndServe(cfg.MetricsAddr, mux); err != nil {
			log.Fatalf("metrics server: %v", err)
		}
	}()

	tailer := newTailer(cfg.InputLog)
	if err := tailer.Start(); err != nil {
		log.Fatalf("tail start: %v", err)
	}
	defer tailer.Stop()

	// handle signals
	sig := make(chan os.Signal, 2)
	signalNotify(sig)

	enc := json.NewEncoder(out)
	enc.SetEscapeHTML(false)

	log.Printf("tailing %s -> %s", cfg.InputLog, cfg.OutputJSONL)

	for {
		select {
		case <-sig:
			log.Printf("shutdown")
			return
		case line, ok := <-tailer.Lines():
			if !ok {
				return
			}
			ev, ok := parser.parse(line)
			if !ok {
				continue
			}

			domain, _ := normalizeHostToDomain(ev.DstHost)
			ev.Domain = domain
			ev.Brand = bm.brand(domain)

			// geo by src ip
			ev.Geo = geo.lookup(ev.SrcIP)

			// watchlist
			if hit, sev, rule := wl.check(ev.User, ev.Domain, ev.Brand, time.Now()); hit {
				ev.WatchHit = true
				ev.Severity = sev
				ev.Rule = rule
				watchHits.WithLabelValues(ev.User, sev, rule).Inc()
			}

			// metrics
			userReq.WithLabelValues(ev.User).Inc()
			userBrandReq.WithLabelValues(ev.User, ev.Brand).Inc()
			userLastSeen.WithLabelValues(ev.User).Set(float64(time.Now().Unix()))

			// write JSONL
			if err := enc.Encode(ev); err != nil {
				log.Printf("write jsonl error: %v", err)
			}
		}
	}
}

func signalNotify(ch chan os.Signal) {
	signal.Notify(ch, syscall.SIGINT, syscall.SIGTERM)
}

