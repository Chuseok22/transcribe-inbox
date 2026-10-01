# Configuration

The launchd daemon reads its settings from the plist's `EnvironmentVariables`. During installation, you copy `launchd/com.chuseok22.transcribe-inbox.plist` and fill in the values below.

## plist keys

| Key | Meaning | Notes |
|---|---|---|
| `ProgramArguments[0]` | Absolute path to `uv` | Check with `which uv` — it varies by how you installed it (Homebrew, the official install script, etc.), so don't carelessly assume `/opt/homebrew/bin/uv` |
| `DATABASE_URL` | PostgreSQL connection string | e.g. `postgresql://user:password@localhost:5432/transcribe_inbox` |
| `WHISPER_CLI_BINARY` | Path to `whisper-cli` | Check with `which whisper-cli` |
| `WHISPER_VAD_MODEL_PATH` | Path to `ggml-silero-v6.2.0.bin` | Where you downloaded it |
| `WHISPER_ASR_MODEL_PATH` | Path to `ggml-large-v3.bin` | Where you downloaded it |
| `WHISPER_MLX_MODEL_PATH` | HuggingFace repository ID | `mlx-community/whisper-large-v3-mlx` is a reasonable default — not a file path |
| `HUGGINGFACE_TOKEN` | The Read-permission token you created | Only needed for the `diarize` mode, but the code reads this value unconditionally whenever it routes to that engine, so if you won't use `diarize`, put in a dummy value anyway |
| `PATH` | Include the directory containing `uv` | launchd does **not inherit** your shell's `PATH` — every binary this daemon shells out to must be findable within the list specified here, and you must not assume it will be on some default `PATH` |

## Path settings (optional)

The input, archive, and output folders can be changed with environment variables. These values are read by the **daemon process**, not by your shell, so they must go in the plist's `EnvironmentVariables`; an `export` in the terminal has no effect.

| Purpose | Environment variable | Default |
|---|---|---|
| Input (watched) folder | `TRANSCRIBE_INBOX_ROOT` | `~/Transcribe/inbox` |
| Original archive folder | `TRANSCRIBE_ARCHIVE_ROOT` | `~/Transcribe/archive` |
| Transcript output folder | `OBSIDIAN_TRANSCRIPTS_ROOT` | `~/Obsidian/second-brain/Transcripts` |

- The output folder does not need to be an Obsidian vault. Only the name says `OBSIDIAN_*`; an ordinary folder works too. The results are `transcript.json`, `.md`, `.txt`, and `.srt` files, so they are usable without Obsidian.
- The temporary working folder (`.staging`) is created under the output folder, so the folder rename at publish time happens within the same volume.
- The original archive folder may be on a different volume from the input folder. The move is handled as copy-then-delete and is not atomic.
- The category name `미분류` (Uncategorized), used for files placed at the inbox root without a category, is hard-coded and cannot be changed.
