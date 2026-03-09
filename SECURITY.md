# Security Policy

## Supported Versions

The latest release branch is considered supported for security fixes.

| Version | Supported |
| ------- | --------- |
| latest  | yes       |
| older   | no        |

## Reporting a Vulnerability

If you discover a security issue, please do not open a public issue with full reproduction details.

Instead, report it privately with:

- affected version
- component or file
- reproduction steps
- impact
- any suggested mitigation

Security-relevant topics include:

- exposed secrets or credentials
- unsafe installer behavior
- privilege escalation paths
- insecure default configuration
- bot authorization bypass
- configuration injection
- unsafe service restart/apply behavior
- monitoring exposure issues
- repository history leaks

## Disclosure Guidance

Please avoid publishing:

- live tokens
- private keys
- full server IP + active credentials
- bot credentials
- unredacted environment files

If the report is valid, the issue will be reviewed and fixed in a future release.

## Hardening Notes

Operators are expected to:

- protect `/etc/mifa/*.env`
- restrict monitoring endpoints where appropriate
- rotate exposed credentials immediately
- review generated configuration before production use
- keep the platform updated to the latest release
