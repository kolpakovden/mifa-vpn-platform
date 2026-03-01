# Contributing

Thank you for your interest in contributing to MIFA VPN Platform.

We welcome improvements, bug fixes, documentation updates, and architectural enhancements.

---

## Development Guidelines

Please follow these rules when contributing:

- Follow **Semantic Versioning (SemVer)**.
- Never commit secrets, tokens, or private keys.
- Keep installer scripts **idempotent** (safe to run multiple times).
- Maintain modular structure (core, bot, monitoring separated).
- Do not introduce telemetry or external tracking.
- Preserve backward compatibility within the same major version.

---

## Code Quality

- Keep changes minimal and focused.
- Avoid unnecessary dependencies.
- Ensure shell scripts are POSIX-safe where possible.
- Test configuration changes with `xray -test` before applying.
- Ensure bot changes fail safely (no unsafe config writes).

---

## Branch Strategy

- `main` → stable production-ready branch
- `feature/*` → new functionality
- `hotfix/*` → urgent patches
- `refactor/*` → internal improvements (optional but recommended)

Pull requests should target `main`.

---

## Pull Request Requirements

Before opening a PR:

- Ensure the platform installs cleanly on Ubuntu.
- Verify that Xray starts without errors.
- Confirm no regression in Telegram bot functionality.
- Update README or documentation if needed.

---

## Security Contributions

If your contribution relates to a security issue:

Do **not** open a public issue.  
Please follow the responsible disclosure process described in `SECURITY.md`.

---

## Philosophy

MIFA VPN Platform exists to enable free and reliable access to the open Internet.

The project is built on the belief that connectivity should not be artificially restricted
by geography, censorship, or infrastructure limitations.

At the same time, MIFA follows strict engineering principles:

- Minimal exposed surface
- Operational simplicity
- Production-grade stability
- Transparent behavior (no telemetry, no hidden tracking)
- Clean and auditable infrastructure design

Freedom of access should not require complex tooling.
MIFA aims to make it simple, secure, and self-hosted.
