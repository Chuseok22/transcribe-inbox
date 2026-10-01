# Contributing to transcribe-inbox

Thanks for your interest! transcribe-inbox is a macOS (Apple Silicon) background daemon that transcribes audio dropped into a folder.

## Development setup

```sh
uv sync
uv run pytest            # unit tests (integration tests are skipped by default)
```

Integration tests (`pytest -m integration`) need PostgreSQL, `ffmpeg`, `whisper-cli`, and the models described in the docs.

## Commit messages

Use `<type>: <description>` with one of `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.

## Pull requests

- Link the related issue.
- Keep changes focused; do not mix refactoring with behavior changes.
- Run `uv run pytest` before opening the PR.

## Documentation and translations

The README exists in three languages (`README.md` English, `README.ko.md` Korean, `README.zh-CN.md` Simplified Chinese), and the docs site in `website/` has the same three languages (`/`, `/ko/`, `/zh/`). Korean is the source of truth for wording. When you change user-facing behavior, update all three READMEs and all three site languages in the same PR, or say in the PR which ones are still pending.

The Chinese translation is AI-generated; corrections are welcome.

To preview the site locally:

```sh
cd website
pnpm install
pnpm dev
```
