# transcribe-inbox

<!-- AUTO-VERSION-SECTION: DO NOT EDIT MANUALLY -->
## Latest Version : v0.3.0 (2026-09-26)

**English** | [한국어](README.ko.md) | [简体中文](README.zh-CN.md)

![Release](https://img.shields.io/github/v/release/Chuseok22/transcribe-inbox)
![License](https://img.shields.io/github/license/Chuseok22/transcribe-inbox)
![Platform](https://img.shields.io/badge/platform-macOS%20(Apple%20Silicon)-lightgrey)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://chuseok22.github.io/transcribe-inbox/)

**Drop audio into a folder. Get a transcript in your notes. Fully local on Apple Silicon.**

> **macOS + Apple Silicon only.** Linux, Windows, and Intel Macs are not supported.

<!-- Demo GIF placeholder: insert after the user provides the recording -->

A local background daemon that watches a folder, automatically transcribes newly added recordings (audio or video), and publishes the results to an Obsidian vault (or a plain folder). It uses a hybrid whisper.cpp / whispermlx engine and makes no cloud API calls.

Any format that `ffmpeg` can decode as audio works, whether it is an audio or a video file. The pipeline does not check file extensions: it only extracts the audio stream with `ffmpeg` and never trims silence, so transcript timestamps always match the original. A file that `ffmpeg` cannot open fails only that job and does not affect the daemon or other jobs.

## Features

- **Fully local, privacy first**: all processing happens on your Mac, with no cloud API calls.
- **Folder structure is the configuration**: the folder depth where you drop a file decides its category and mode. No config file and no filename rules.
- **Three modes**: `asr` for a single speaker, `asr-multitrack` to merge per-speaker tracks, and `diarize` to tell apart multiple speakers in one file.
- **Idempotent queueing and state recovery**: files are identified by content hash, so identical content is never queued twice, and the daemon settles the state of interrupted jobs by itself after a restart.
- **Verbatim output, no summarizing**: results come out as `transcript.json` (the source of truth), `.md`, `.txt`, and `.srt`. Summarizing is up to you.
- **Works with any folder, not just Obsidian**: output is plain Markdown/JSON/SRT files written to a regular folder, so any tool can open them.

## How it works

Once a file lands in the inbox, it is processed in the following order. Jobs run one at a time.

```mermaid
flowchart LR
  A["Drop a file into ~/Transcribe/inbox/"] --> B["watchdog: wait for size to settle"]
  B --> C[("PostgreSQL job queue")]
  C --> D["Worker: one job at a time"]
  D --> E["ffmpeg: 16kHz mono WAV"]
  E --> F{"Mode"}
  F -->|"asr / asr-multitrack"| G["whisper.cpp"]
  F -->|"diarize"| H["whispermlx"]
  G --> I["Publish transcript.json · .md · .txt · .srt"]
  H --> I
  I --> J["Move original to archive + macOS notification"]
```

## Requirements

- macOS + Apple Silicon
- PostgreSQL running locally (job queue and state store)
- `ffmpeg`
- `whisper-cli` (whisper.cpp) and two model files (the ASR model `ggml-large-v3.bin` and the VAD model `ggml-silero-v6.2.0.bin`)
- `uv` (to install Python dependencies)
- `diarize` mode only: a HuggingFace **Read** token and acceptance of the diarization model terms

For per-item install steps, see [Prerequisites](https://chuseok22.github.io/transcribe-inbox/getting-started/prerequisites) and the [Installation guide](https://chuseok22.github.io/transcribe-inbox/getting-started/installation).

## Quick start

These are the minimal steps for a first-time install. Once installed, just drop recordings under `~/Transcribe/inbox/`.

You first need to create the PostgreSQL database, apply the schema, and download the two models — see the [Installation guide](https://chuseok22.github.io/transcribe-inbox/getting-started/installation).

```sh
brew install ffmpeg whisper-cpp
uv sync   # for DB schema and model downloads, see the installation guide
cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist   # fill in the values
cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
```

The daemon will not run until you fill in the plist with the absolute paths of `uv`, `whisper-cli`, and the model files, plus `DATABASE_URL` and the like. For detailed configuration, see the [documentation](https://chuseok22.github.io/transcribe-inbox/).

## Documentation

The full documentation is at [https://chuseok22.github.io/transcribe-inbox/](https://chuseok22.github.io/transcribe-inbox/).

- **Getting started**: [Prerequisites](https://chuseok22.github.io/transcribe-inbox/getting-started/prerequisites), [Installation](https://chuseok22.github.io/transcribe-inbox/getting-started/installation)
- **Guide**: [Inbox folder layout](https://chuseok22.github.io/transcribe-inbox/guide/inbox-layout), [Modes](https://chuseok22.github.io/transcribe-inbox/guide/modes), [Usage](https://chuseok22.github.io/transcribe-inbox/guide/usage)
- **Reference**: [Configuration](https://chuseok22.github.io/transcribe-inbox/reference/configuration), [Output format](https://chuseok22.github.io/transcribe-inbox/reference/output)
- **Help**: [Troubleshooting](https://chuseok22.github.io/transcribe-inbox/help/troubleshooting), [Known limitations](https://chuseok22.github.io/transcribe-inbox/help/known-limitations)

## Known limitations

The currently known limitations are:

- whisper.cpp is not pinned to a specific git tag/commit, so behavior may change when the `stable` version installed by `brew install whisper-cpp` changes.
- `diarize` mode has not yet been through an end-to-end test on real recordings. Run a smoke test before relying on it.
- If two different recordings resolve to the same category and label, the transcript output directory is overwritten. The original audio is protected by a content-hash suffix, but the transcripts are not yet.
- `HUGGINGFACE_TOKEN` must be placed directly in the (gitignored) plist file; Keychain and a separate secrets file are not supported yet.
- Files placed directly in the inbox root get the category name `미분류` (Uncategorized), which is hardcoded and cannot be changed.
- Transcription language is currently fixed to Korean (`language="ko"` in the worker, `-l ko` for whisper.cpp); other languages cannot be configured yet.

For details, see the [Known limitations](https://chuseok22.github.io/transcribe-inbox/help/known-limitations) page.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute. When editing the README, treat Korean (`README.ko.md`) as the source and update the English and Chinese translations together.

## License

MIT — [LICENSE](LICENSE)
