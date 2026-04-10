# Contributing

## Development Setup

1. Install dependencies with `poetry install`.
2. Copy `.env.example` to `.env`.
3. Provide your own Telegram API credentials and channel list.
4. Run tests with `poetry run pytest`.

## Pull Requests

- Keep changes scoped to one problem.
- Include tests for behavior changes when practical.
- Update documentation when configuration, behavior, or developer workflows change.
- Do not include secrets, session files, local database dumps, or machine-specific paths.

## Code Style

- Prefer small, composable functions.
- Preserve backwards compatibility for environment variables unless there is a strong reason to break it.
- Keep optional integrations disabled by default.

## Reporting Issues

- Include reproduction steps.
- Include relevant environment details such as Python version and enabled providers.
- Redact credentials, URIs with embedded passwords, and any private channel information.
