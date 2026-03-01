import os
import time
import json
import requests
from urllib.parse import urlparse, urlunparse

from flask import Flask, request, jsonify

app = Flask(__name__)

def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.environ.get(name, "") or "").strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default

def _env_int(name: str, default: int) -> int:
    v = (os.environ.get(name, "") or "").strip()
    try:
        return int(v)
    except Exception:
        return default

def _get_cfg():
    token = (os.environ.get("TG_BOT_TOKEN", "") or "").strip()
    chat_id = (os.environ.get("TG_CHAT_ID", "") or "").strip()
    send_resolved = _env_bool("SEND_RESOLVED", False)

    public_prom = (os.environ.get("PUBLIC_PROMETHEUS_URL", "") or "").strip().rstrip("/")
    loki_url = (os.environ.get("LOKI_URL", "http://loki:3100") or "").strip().rstrip("/")
    lookback_min = _env_int("LOKI_LOOKBACK_MINUTES", 30)

    return token, chat_id, send_resolved, public_prom, loki_url, lookback_min

def _sev_emoji(sev: str) -> str:
    s = (sev or "").strip().lower()
    if s == "critical":
        return "🚨"
    if s in ("warn", "warning"):
        return "⚠️"
    if s in ("info", "informational"):
        return "ℹ️"
    return "🔔"

def tg_send(text: str):
    token, chat_id, *_ = _get_cfg()
    if not token or not chat_id:
        print("tg_send: missing TG_BOT_TOKEN or TG_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=8)
        print("tg_send:", r.status_code, r.text[:200])
    except Exception as e:
        print("tg_send error:", repr(e))

def _trim(s: str, n: int) -> str:
    s = s or ""
    if len(s) <= n:
        return s
    return s[:n] + "…"

def _rewrite_generator_url(generator: str, public_prom: str) -> str:
    """
    Alertmanager/Prometheus часто кладёт generatorURL вида http://prometheus:9090/...
    Снаружи это не открывается. Если PUBLIC_PROMETHEUS_URL задан — переписываем scheme+host+port.
    """
    if not generator:
        return ""
    if not public_prom:
        return generator

    try:
        pu = urlparse(public_prom)
        gu = urlparse(generator)

        # если generator без http — не трогаем
        if not gu.scheme or not gu.netloc:
            return generator

        # переписываем на public (scheme+netloc), путь/параметры оставляем
        return urlunparse((pu.scheme, pu.netloc, gu.path, gu.params, gu.query, gu.fragment))
    except Exception:
        return generator

def _is_watchlist_alert(alertname: str) -> bool:
    a = (alertname or "").strip().lower()
    return "watchlist" in a

def _loki_fetch_watch_context(loki_url: str, user: str, lookback_min: int):
    """
    Достаём последний лог из Loki по пользователю, где встречается '"watch_hit":true'
    (мы сознательно делаем простую строковую фильтрацию, т.к. pipeline может отличаться).
    """
    if not loki_url or not user:
        return None

    now_ns = int(time.time() * 1e9)
    start_ns = now_ns - int(lookback_min * 60 * 1e9)

    query = f'{{job="mifa-traffic", user="{user}"}} |= "\\\"watch_hit\\\":true"'

    params = {
        "query": query,
        "start": str(start_ns),
        "end": str(now_ns),
        "limit": "1",
        "direction": "BACKWARD",
    }

    try:
        r = requests.get(f"{loki_url}/loki/api/v1/query_range", params=params, timeout=5)
        if r.status_code != 200:
            print("loki ctx bad status:", r.status_code, r.text[:200])
            return None

        payload = r.json()
        res = (((payload.get("data") or {}).get("result")) or [])
        if not res:
            return None

        values = (res[0].get("values") or [])
        if not values:
            return None

        # values: [[ts, "line"], ...]
        line = values[0][1]
        ev = json.loads(line)

        geo = ev.get("geo") or {}
        return {
            "domain": ev.get("domain") or "",
            "dst_host": ev.get("dst_host") or "",
            "src_ip": ev.get("src_ip") or "",
            "city": geo.get("city") or "",
            "region": geo.get("region") or "",
            "country": geo.get("country") or "",
            "isp": geo.get("isp") or "",
            "asn_org": geo.get("asn_org") or "",
        }
    except Exception as e:
        print("loki ctx error:", repr(e))
        return None

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.post("/alertmanager")
def alertmanager_webhook():
    data = request.get_json(silent=True) or {}
    alerts = data.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []

    token, chat_id, send_resolved, public_prom, loki_url, lookback_min = _get_cfg()
    if not token or not chat_id:
        # 200 чтобы Alertmanager не ретраил бесконечно
        return jsonify({"ok": False, "error": "missing TG_BOT_TOKEN/TG_CHAT_ID"}), 200

    # Умная группировка: (status, severity, user)
    groups = {}
    received = len(alerts)
    considered = 0

    for a in alerts:
        try:
            status = (a.get("status") or "").strip().lower()  # firing/resolved
            if status == "resolved" and not send_resolved:
                continue
            if status not in ("firing", "resolved"):
                continue

            labels = a.get("labels") or {}
            ann = a.get("annotations") or {}

            alertname = labels.get("alertname", "Alert")
            severity = labels.get("severity", "unknown")
            user = labels.get("user", "")  # ключевая группировка
            rule = labels.get("rule", "")
            job = labels.get("job", "")
            instance = labels.get("instance", "")
            generator = a.get("generatorURL") or ""

            generator = _rewrite_generator_url(generator, public_prom)

            key = (status, severity, user or "unknown")
            groups.setdefault(key, {
                "status": status,
                "severity": severity,
                "user": user or "unknown",
                "items": [],
                "job": job,
                "instance": instance,
                "generator": generator,
            })

            summary = (ann.get("summary") or "").strip()
            desc = (ann.get("description") or "").strip()
            body = summary if summary else desc

            groups[key]["items"].append({
                "alertname": alertname,
                "rule": rule,
                "body": body,
                "job": job,
                "instance": instance,
                "generator": generator,
            })

            considered += 1
        except Exception as e:
            key = ("firing", "unknown", "unknown")
            groups.setdefault(key, {"status":"firing","severity":"unknown","user":"unknown","items":[],"job":"","instance":"","generator":""})
            groups[key]["items"].append({"alertname":"ParseError","rule":"","body":repr(e),"job":"","instance":"","generator":""})
            considered += 1

    if not groups:
        return jsonify({"ok": True, "received": received, "sent_groups": 0}), 200

    # Отправляем по одному сообщению на группу — это и есть “умное” снижение спама.
    sent_groups = 0

    for (status, severity, user), g in groups.items():
        emoji = _sev_emoji(severity)
        state_emoji = "🔥" if status == "firing" else "✅"

        header = f"{emoji} {severity.upper()} {state_emoji} | user={user}"
        lines = [header]

        # контекст из Loki только для watchlist-алертов (и только для firing — обычно так полезнее)
        wants_ctx = (status == "firing") and any(_is_watchlist_alert(it.get("alertname","")) for it in g["items"])
        if wants_ctx:
            ctx = _loki_fetch_watch_context(loki_url, user, lookback_min)
            if ctx:
                ctx_line = "📌 last hit: "
                dom = ctx.get("domain") or ctx.get("dst_host") or ""
                if dom:
                    ctx_line += f"{dom}"
                geo_parts = [p for p in [ctx.get("city"), ctx.get("region"), ctx.get("country")] if p]
                if geo_parts:
                    ctx_line += " | " + ", ".join(geo_parts)
                isp = ctx.get("isp") or ctx.get("asn_org") or ""
                if isp:
                    ctx_line += f" | {isp}"
                src = ctx.get("src_ip") or ""
                if src:
                    ctx_line += f" | src_ip={src}"
                lines.append(ctx_line)

        # перечислим элементы группы (аккуратно)
        for it in g["items"][:8]:  # ограничим, чтобы не раздулось
            name = it.get("alertname", "Alert")
            rule = it.get("rule", "")
            body = (it.get("body") or "").strip()

            item_head = f"• {name}"
            if rule:
                item_head += f" (rule={rule})"
            lines.append(item_head)
            if body:
                lines.append(_trim(body, 500))

        if len(g["items"]) > 8:
            lines.append(f"… +{len(g['items'])-8} more")

        # generatorURL — берём первый непустой
        gen = ""
        for it in g["items"]:
            if it.get("generator"):
                gen = it["generator"]
                break
        if gen:
            lines.append(f"🔗 {gen}")

        msg = _trim("\n".join(lines), 3500)
        tg_send(msg)
        sent_groups += 1

    return jsonify({"ok": True, "received": received, "considered": considered, "sent_groups": sent_groups}), 200
