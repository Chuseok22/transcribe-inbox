# transcribe-inbox

A local-only macOS background daemon that watches a folder for dropped-in
recordings (lecture/meeting audio **or video**), transcribes them on Apple
Silicon GPU using a hybrid whisper.cpp/whispermlx engine, and publishes the
transcript into an Obsidian vault. No cloud API calls — everything runs
locally. There is no summarization step; that's left to the user.

## How it works

```
Drop a file into ~/Transcribe/inbox/<category>/[mode]/...
  → watchdog detects it, waits for it to stop growing (stabilization check)
  → registered as a job in PostgreSQL (idempotent — same content is never re-queued)
  → worker claims the job (one at a time — no concurrent GPU jobs)
  → ffmpeg extracts/resamples the audio to 16kHz mono WAV
    (works on audio AND video containers — see "Supported input formats" below;
    never trims silence, so the transcript's timestamps always match the original)
  → routed to an engine by mode:
      asr / asr-multitrack → whisper.cpp (single-speaker or pre-separated tracks)
      diarize               → whispermlx (mixed-speaker meetings, adds speaker labels)
  → transcript.json (canonical) + .md/.txt/.srt published to the Obsidian vault
  → original file archived, macOS notification sent
```

If the daemon restarts (crash, reboot), it reconciles on startup: jobs stuck
mid-processing are requeued (or marked failed if the source vanished), and
completed jobs whose source never made it to the archive folder get
archived then.

## Supported input formats

Audio or video — **anything `ffmpeg` can decode audio from**. The pipeline
never inspects file extensions; it just runs `ffmpeg -i <file> -ar 16000 -ac 1
<wav>`, which extracts and resamples whatever audio stream `ffmpeg` finds,
regardless of container. Verified directly: `.m4a` (Galaxy voice recorder),
and `.mp4`/`.mov`-style video containers with an embedded audio track both
work — `ffmpeg` extracts just the audio track and the rest of the pipeline
never sees the video stream. A file `ffmpeg` can't demux at all (corrupted,
unsupported codec) fails that one job with a clear error in the database;
it won't crash the daemon or affect other jobs.

## Prerequisites

- PostgreSQL running locally (job queue/state store — transcript content
  itself is never stored here, only job status/metadata)
- `ffmpeg`:
  ```sh
  brew install ffmpeg
  ```
- `whisper-cli` (whisper.cpp's CLI binary) — **not** a PyPI package:
  ```sh
  brew install whisper-cpp
  which whisper-cli   # confirm the install path, used below
  ```
  This project does not yet pin an exact whisper.cpp git tag/commit, so
  `brew`'s `stable` version is what you get; that's a known gap.
- Two whisper.cpp model files, downloaded individually (not the whole
  HuggingFace repo — those repos bundle every model size/quantization and
  are tens of GB in total):
  - ASR model: [`ggml-large-v3.bin`](https://huggingface.co/ggerganov/whisper.cpp/tree/main)
    (this project is fixed to `large-v3`, unquantized, for accuracy — a few
    GB)
  - VAD model: [`ggml-silero-v6.2.0.bin`](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin)
    (a **different** HuggingFace repo than the ASR model — under 1MB)
- `whispermlx` (used for `diarize` mode) — installed automatically by
  `uv sync` below, no separate step. Its actual ASR/alignment/diarization
  models are **not** local files you download — `whispermlx` pulls them
  from HuggingFace on first use and caches them under
  `~/.cache/huggingface/`, keyed by a model name like
  `mlx-community/whisper-large-v3-mlx` (that string is what
  `WHISPER_MLX_MODEL_PATH` below actually holds — despite the "PATH" in the
  name, it's a HuggingFace repo ID, not a filesystem path).
- A HuggingFace access token, if you'll use `diarize` mode (mixed-speaker
  meetings) — the diarization model is gated:
  1. Create a **Read**-scope token at huggingface.co → Settings → Access
     Tokens (Read is sufficient; this project only downloads/uses models,
     never uploads anything).
  2. Visit https://huggingface.co/pyannote/speaker-diarization-community-1
     and accept the model's terms — without this, diarization fails at
     runtime even with a valid token.
- macOS `osascript` (already present on any Mac; used for notifications)

## Setup

1. Install Python dependencies (creates an isolated `.venv/` automatically,
   pinned to the versions in `uv.lock`):
   ```sh
   uv sync
   ```
2. Create a database and apply the schema. If PostgreSQL is running in
   Docker without a local `psql` client installed, run `psql` inside the
   container instead:
   ```sh
   # create the database (adjust the container name/user for your setup)
   docker exec <container> psql -U <user> -d postgres -c "CREATE DATABASE transcribe_inbox"
   # apply the schema
   docker exec -i <container> psql -U <user> -d transcribe_inbox < src/transcribe_inbox/db/schema.sql
   ```
   (If you have a local `psql` client and a non-Docker PostgreSQL, the
   equivalent is `createdb transcribe_inbox && psql "$DATABASE_URL" -f
   src/transcribe_inbox/db/schema.sql`.)
3. Copy the plist template and fill in real values — **never edit or commit
   the tracked `.example` file with real credentials**; the real plist is
   gitignored specifically so this can't happen by accident:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist
   ```
   Edit `launchd/com.chuseok22.transcribe-inbox.plist` and replace every
   `YOUR_USERNAME`/placeholder with real values:

   | Key | What it is | Notes |
   |---|---|---|
   | `ProgramArguments[0]` | Absolute path to `uv` | `which uv` — this varies by install method (Homebrew, the official installer script, etc.), so don't assume `/opt/homebrew/bin/uv` |
   | `DATABASE_URL` | PostgreSQL connection string | e.g. `postgresql://user:password@localhost:5432/transcribe_inbox` |
   | `WHISPER_CLI_BINARY` | Path to `whisper-cli` | `which whisper-cli` |
   | `WHISPER_VAD_MODEL_PATH` | Path to `ggml-silero-v6.2.0.bin` | wherever you downloaded it |
   | `WHISPER_ASR_MODEL_PATH` | Path to `ggml-large-v3.bin` | wherever you downloaded it |
   | `WHISPER_MLX_MODEL_PATH` | HuggingFace repo ID | `mlx-community/whisper-large-v3-mlx` is a reasonable default; not a filesystem path |
   | `HUGGINGFACE_TOKEN` | Your Read-scope token | only needed for `diarize` mode, but the code reads it unconditionally when routing to that engine, so leave a value here (even a dummy one) if you won't use `diarize` |
   | `PATH` | Include the directory containing `uv` | launchd does **not** inherit your shell's `PATH` — every binary this daemon shells out to must be reachable via this exact list, not assumed to be on some default `PATH` |

   Every one of these is read by the *daemon process*, not your shell — a
   terminal `export` has no effect on it. These values only need to exist
   inside this plist file.
4. Install and start the daemon:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. Verify it's actually running (a copied plist doesn't guarantee a running
   process — if any path above is wrong, launchd fails silently in the
   sense that nothing gets logged, since the process never starts):
   ```sh
   launchctl list | grep transcribe-inbox
   ```
   The first column is a PID if it's running, or `-` if it's not (the
   second column is the last exit status). If it's not running, check both
   log files — though note that **launchd runtime failures (a wrong binary
   path, etc.) produce empty logs**, since the Python process never even
   starts to write anything:
   ```sh
   cat ~/Library/Logs/transcribe-inbox.log
   cat ~/Library/Logs/transcribe-inbox.error.log
   ```
   If both are empty and the daemon still isn't running, the most likely
   cause is a wrong absolute path somewhere in the plist (`uv`, `whisper-cli`,
   a model file) — re-check every path with `which`/`ls`. After editing the
   plist, you must `launchctl unload` then `launchctl load` again; overwriting
   the file alone does not reload it.

## Inbox folder structure

Drop files under `~/Transcribe/inbox/<category>/[mode]/<file-or-session>`:

- `~/Transcribe/inbox/강의/2주차.m4a` → category `강의`, mode `asr` (default —
  omit the mode folder entirely for single-speaker recordings)
- `~/Transcribe/inbox/회의/diarize/2026-09-08.m4a` → category `회의`, mode
  `diarize` (mixed-speaker meeting — adds speaker labels via whispermlx)
- `~/Transcribe/inbox/회의/asr-multitrack/2026-09-08/김철수.m4a` (+ other
  per-speaker files in the same session folder) → mode `asr-multitrack`,
  processed as one job covering the whole session

The mode is determined by folder structure alone — there's no way to set a
persistent "this category is always diarize" default; every file's mode is
whatever folder path it's dropped under. `~/Transcribe/archive/` (originals)
and any other folder outside `~/Transcribe/inbox/` are never watched, even
as siblings — safe to store anything else there, including downloaded
models (e.g. `~/Transcribe/model/`).

Ambiguous paths (wrong nesting depth, an unrecognized mode name) are
skipped and logged, never guessed at.

## Usage

Drop a file into the inbox — it's picked up automatically. Once done:

- The transcript is published to
  `~/Obsidian/second-brain/Transcripts/<category>/<label>/` as
  `transcript.json` (canonical, includes per-segment/per-word timestamps
  and speaker labels where applicable), `transcript.md`, `transcript.txt`,
  and `transcript.srt`.
- The original file is moved to `~/Transcribe/archive/<category>/<mode>/`.
  If a file with the same name already exists there, the new one is never
  overwritten — it's saved under a content-hash-suffixed name instead, so
  no original is ever silently lost.
- A macOS notification fires on completion or failure.

To retry a job that failed (its source file must still exist):

```sh
transcribe-inbox retry <job-id>
```

Job status/history lives in PostgreSQL, not in any log file — the quickest
way to check what happened to a specific job:

```sh
psql "$DATABASE_URL" -c "SELECT id, status, error_message, created_at FROM transcription_job ORDER BY created_at DESC LIMIT 10;"
```

## Known limitations

- whisper.cpp isn't pinned to a specific git tag/commit yet — `brew install
  whisper-cpp` tracks upstream `stable`, which could change behavior on a
  future upgrade with no warning.
- `diarize` mode hasn't been run end-to-end against a real recording on this
  machine yet (no `whisper-cli`/models were installed during development) —
  the code path was fixed based on reading the real `whispermlx` library
  source, but a live smoke test is still worth doing before relying on it.
- If two *different* recordings end up with the same category+label (not a
  re-run of the same job — a genuine filename collision), the transcript
  directory is overwritten. The original *audio* is protected against this
  (content-hash-suffixed on collision, see above); the transcript itself
  currently is not.
- `HUGGINGFACE_TOKEN` must currently be placed directly in the (gitignored)
  plist file — there's no support yet for pulling it from macOS Keychain or
  a separate secrets file.
