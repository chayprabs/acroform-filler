# Security Policy

## Supported versions

Only the latest `main` branch and tagged releases are supported.

## Reporting a vulnerability

Please use GitHub Security Advisories for private disclosure.

Include:

- Affected endpoint or UI flow
- Reproduction steps
- Potential impact
- Suggested remediation (if available)

## Security defaults

- Passwords are never persisted in job metadata.
- Artifact downloads are signed and expire using TTL.
- Uploads are scoped to ephemeral job directories.
