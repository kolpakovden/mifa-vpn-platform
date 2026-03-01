# Security Policy

## Supported Versions

The following versions of MIFA VPN Platform are currently supported with security updates:

| Version | Supported |
|---------|----------|
| 1.x     | ✅ Yes   |
| legacy  | ❌ No    |

Only the latest minor release within the 1.x branch receives security updates.

---

## Reporting a Vulnerability

If you discover a security vulnerability, please follow responsible disclosure:

1. **Do NOT open a public GitHub issue.**
2. Contact the maintainer directly via GitHub or private communication.
3. Provide:
   - Detailed reproduction steps
   - Affected version
   - Impact assessment (if known)
   - Logs or configuration snippets (sanitized)

Initial response within 72 hours.

Security issues will be addressed as quickly as possible, and a patched release will be published.

---

## Security Design Principles

MIFA VPN Platform is designed with the following security model:

- No public web admin panel
- Telegram-based restricted administrative access
- Role-restricted bot access (ADMIN_IDS / ALLOWED_CHAT_ID)
- Reality TLS obfuscation (Xray Reality)
- Minimal exposed network surface
- No telemetry or external data collection
- Safe configuration apply (backup → test → restart → rollback)

---

## Operational Recommendations

For production deployments:

- Restrict Prometheus, Loki, and Node Exporter via firewall
- Expose Grafana only if properly secured
- Use strong, private Telegram bot tokens
- Keep the system updated
- Rotate keys if compromise is suspected
