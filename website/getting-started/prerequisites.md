# Prerequisites

## Supported input formats

Audio or video, it doesn't matter — **any format `ffmpeg` can decode audio from** is supported. The pipeline never checks file extensions; it simply runs `ffmpeg -i <file> -ar 16000 -ac 1 <wav>`. Regardless of the container type, this command extracts and resamples whatever audio stream `ffmpeg` finds. What has been verified directly: both `.m4a` (files from the Galaxy voice recorder) and `.mp4`/`.mov`-family video containers that include an audio track work correctly — `ffmpeg` extracts only the audio track, and the rest of the pipeline never looks at the video stream at all. A file that `ffmpeg` cannot even demux (corrupted, or using an unsupported codec) fails only that one job, with a clear error recorded in the DB; the daemon does not crash and other jobs are unaffected.

## What you need

- A locally running PostgreSQL (the job queue / state store — the transcript content itself is not stored here, only job status and metadata)
- `ffmpeg`:
  ```sh
  brew install ffmpeg
  ```
- `whisper-cli` (the CLI binary from whisper.cpp) — this is **not** a PyPI package:
  ```sh
  brew install whisper-cpp
  which whisper-cli   # 설치 경로 확인, 아래에서 사용됨
  ```
  (Comment in the block: check the install path, used below.)
  This project does not yet pin a specific git tag/commit of whisper.cpp, so you get the `stable` version from `brew` as-is — a known gap.
- Two whisper.cpp model files, which you must download individually (do not download the whole HuggingFace repositories — those repositories bundle every model size/quantization variant and add up to tens of GB in total):
  - ASR model: [`ggml-large-v3.bin`](https://huggingface.co/ggerganov/whisper.cpp/tree/main) (this project is fixed to the unquantized `large-v3` for accuracy — several GB)
  - VAD model: [`ggml-silero-v6.2.0.bin`](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin) (from a **different** HuggingFace repository than the ASR model — under 1MB)
- `whispermlx` (used by the `diarize` mode) — installed automatically by `uv sync` in [Installation](/getting-started/installation), so no separate install step is needed. The actual ASR/alignment/diarization models are **not** local files you download yourself — `whispermlx` fetches them from HuggingFace automatically on first use and caches them under `~/.cache/huggingface/`, identified by a model name such as `mlx-community/whisper-large-v3-mlx` (this string is exactly what goes into `WHISPER_MLX_MODEL_PATH` in [Configuration](/reference/configuration) — despite "PATH" in the name, it is a HuggingFace repository ID, not a file path).
- If you use the `diarize` mode (multi-speaker meetings), you need a HuggingFace access token — because the diarization model is a gated (approval-required) model:
  1. In huggingface.co → Settings → Access Tokens, create a token with **Read** permission (Read is enough — this project only downloads/uses models and never uploads anything).
  2. Visit https://huggingface.co/pyannote/speaker-diarization-community-1 and accept the model's terms of use — without this step, diarization fails at runtime even with a valid token.
- macOS `osascript` (built into every Mac; used for sending notifications)
