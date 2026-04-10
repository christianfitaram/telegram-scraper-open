# Security Policy

## Supported Versions

Security fixes are applied to the latest maintained version of the project.

## Reporting a Vulnerability

- Do not open a public issue for a suspected secret leak or exploitable flaw.
- Report the issue privately to the project maintainers.
- Include affected files, reproduction steps, impact, and any suggested mitigation.

## Secrets Handling

- Never commit `.env`, Telegram session files, or database exports.
- Rotate any credential immediately if it is exposed in a local branch, CI log, screenshot, or published history.
- Use `.env.example` for placeholders only.
