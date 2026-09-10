# transcribe-inbox

A local-only macOS background daemon that watches a folder for dropped-in
audio files (lecture/meeting recordings), transcribes them on Apple Silicon
GPU using whisper.cpp or whispermlx, and publishes the transcript into an
Obsidian vault. No cloud API calls — everything runs locally. There is no
summarization step; that's left to the user.

## Prerequisites

- PostgreSQL running locally (used as the job queue/state store)
- `ffmpeg` (audio normalization before transcription)
- `whisper-cli` (whisper.cpp's CLI binary) — **not** a PyPI package, must be
  built/installed separately. This project does not yet pin an exact
  git tag/commit for whisper.cpp; that's a known gap.
- whisper.cpp VAD and ASR GGML models (e.g. `ggml-silero-v6.2.0.bin`,
  `ggml-large-v3.bin`)
- macOS `say`/`osascript` (already present on any Mac; used for
  notifications)
- A HuggingFace access token with access to the gated pyannote diarization
  models, if you'll use `diarize` mode

## Setup

1. Install dependencies:
   ```sh
   uv sync
   ```
2. Apply the schema to a database (name it to match `DATABASE_URL` below,
   e.g. `transcribe_inbox`):
   ```sh
   psql "$DATABASE_URL" -f src/transcribe_inbox/db/schema.sql
   ```
3. Set the required environment variables:
   - `DATABASE_URL` — e.g. `postgresql://user:password@localhost/transcribe_inbox`
   - `WHISPER_CLI_BINARY` — path to the whisper.cpp `whisper-cli` binary
   - `WHISPER_VAD_MODEL_PATH` — path to the whisper.cpp VAD GGML model
   - `WHISPER_ASR_MODEL_PATH` — path to the whisper.cpp ASR GGML model
   - `WHISPER_MLX_MODEL_PATH` — path to the whispermlx model directory
   - `HUGGINGFACE_TOKEN` — required for `diarize` mode (pyannote diarization
     models); never hardcode this in the launchd plist
4. Install the launchd plist to run the daemon in the background:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
   Edit the plist's `EnvironmentVariables` first — the checked-in
   `DATABASE_URL` placeholder has no credentials and won't connect against a
   typical local Postgres setup (e.g. Docker with a non-default user).

## Inbox folder structure

Drop files under `~/Transcribe/inbox/<category>/[mode]/<file-or-session>`,
where `mode` is `asr` (default, omit the folder), `diarize`, or
`asr-multitrack` (a folder of per-speaker track files). See
`docs/superpowers/specs/2026-09-09-transcribe-inbox-design.md` for the full
rationale behind this structure.

## Usage

Drop a file into the inbox — it's picked up automatically, transcribed, and
published to the configured Obsidian vault location. The original is moved
to `~/Transcribe/archive/` once done.

To retry a job that failed:

```sh
transcribe-inbox retry <job-id>
```
