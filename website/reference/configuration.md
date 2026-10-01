# Configuration

The launchd daemon reads its settings from `EnvironmentVariables` in the plist. During installation you copy `launchd/com.chuseok22.transcribe-inbox.plist` and fill in the values below.

## plist keys

| Key | Meaning | Notes |
|---|---|---|
| `ProgramArguments[0]` | Absolute path to `uv` | Check with `which uv`. The path depends on how you installed it (Homebrew, the official install script and so on), so do not assume `/opt/homebrew/bin/uv` |
| `DATABASE_URL` | PostgreSQL connection string | e.g. `postgresql://user:password@localhost:5432/transcribe_inbox` |
| `WHISPER_CLI_BINARY` | Path to `whisper-cli` | Check with `which whisper-cli` |
| `WHISPER_VAD_MODEL_PATH` | Path to `ggml-silero-v6.2.0.bin` | Where you downloaded it |
| `WHISPER_ASR_MODEL_PATH` | Path to `ggml-large-v3.bin` | Where you downloaded it |
| `WHISPER_MLX_MODEL_PATH` | HuggingFace repository ID | Not a file path. `mlx-community/whisper-large-v3-mlx` is a sensible default |
| `HUGGINGFACE_TOKEN` | The Read token you created | Needed only for `diarize` mode. The code always reads this value when it routes to that engine, so put in a dummy value even if you do not use `diarize` |
| `PATH` | Includes the directory that contains `uv` | launchd does not inherit your shell's `PATH`. Every external binary the daemon runs must be found in the directories listed here. Do not assume it is on a default `PATH` |

## Path settings (optional)

You can change the input, archive and output folders with environment variables. The daemon process reads these values, not your shell. Put them in the plist's `EnvironmentVariables`. An `export` in the terminal has no effect.

| Purpose | Environment variable | Default |
|---|---|---|
| Input (watched) folder | `TRANSCRIBE_INBOX_ROOT` | `~/Transcribe/inbox` |
| Archive folder for originals | `TRANSCRIBE_ARCHIVE_ROOT` | `~/Transcribe/archive` |
| Transcript output folder | `OBSIDIAN_TRANSCRIPTS_ROOT` | `~/Obsidian/second-brain/Transcripts` |

- The output folder does not have to be an Obsidian vault. The variable is named `OBSIDIAN_*`, but a plain folder works. The results are `transcript.json`, `.md`, `.txt` and `.srt` files, so you can use them without Obsidian.
- The temporary working folder (`.staging`) is created under the output folder. The rename that saves the results therefore happens within one volume.
- The archive folder can be on a different volume from the input folder. On a different volume the move is a copy followed by a delete, so it is not atomic.
- Files placed at the inbox root without a category get the category name `미분류` (Uncategorized). The name is hard-coded and cannot be changed.
