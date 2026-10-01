# Prerequisites

## Supported input formats

Any audio or video format works as long as `ffmpeg` can decode its audio. The
pipeline does not check file extensions. It runs
`ffmpeg -i <file> -ar 16000 -ac 1 <wav>`, which extracts and resamples the audio
stream `ffmpeg` finds, whatever the container.

Formats tested directly: `.m4a` (files from the Galaxy voice recorder) and
`.mp4`/`.mov`-family video containers with an audio track. For video, `ffmpeg`
extracts only the audio track, and later steps do not touch the video stream.

If a file is corrupted or uses an unsupported codec and `ffmpeg` cannot demux it,
only that job fails and the error is recorded in the DB. The daemon keeps running
and other jobs are not affected.

## What you need

- PostgreSQL running locally. It serves as the job queue and state store. It holds
  job status and metadata only, not transcript content.
- `ffmpeg`:
  ```sh
  brew install ffmpeg
  ```
- `whisper-cli` (the CLI binary of whisper.cpp). It is not a PyPI package.
  ```sh
  brew install whisper-cpp
  which whisper-cli   # 설치 경로 확인, 아래에서 사용됨
  ```
  The comment says: check the install path, used later.
  This project does not pin a specific git tag or commit of whisper.cpp yet, so
  you get the `stable` version from `brew`. This is a known limitation.
- Two whisper.cpp model files. Download each file on its own. Do not download the
  whole HuggingFace repositories: they contain every model size and quantization
  and add up to tens of GB.
  - ASR model: [`ggml-large-v3.bin`](https://huggingface.co/ggerganov/whisper.cpp/tree/main).
    The project uses the unquantized `large-v3` for accuracy. It is several GB.
  - VAD model: [`ggml-silero-v6.2.0.bin`](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin).
    It lives in a different HuggingFace repository from the ASR model. It is under 1MB.
- `whispermlx` (used by `diarize` mode). `uv sync` in
  [Installation](/getting-started/installation) installs it, so there is no
  separate step. The ASR, alignment and diarization models are not local files you
  download. `whispermlx` fetches them from HuggingFace on first use, caches them
  under `~/.cache/huggingface/` and identifies them by a model name such as
  `mlx-community/whisper-large-v3-mlx`. That string is the value of
  `WHISPER_MLX_MODEL_PATH` in [Configuration](/reference/configuration). The name
  contains "PATH", but the value is a HuggingFace repository ID, not a file path.
- For `diarize` mode (meetings with several speakers), a HuggingFace access token.
  The diarization model is gated and needs approval.
  1. On huggingface.co, go to Settings → Access Tokens and create a token with
     Read permission. Read is enough, because this project only downloads and
     uses models and does not upload anything.
  2. Accept the model's terms of use at
     https://huggingface.co/pyannote/speaker-diarization-community-1. Without
     this, diarization fails at runtime even with a valid token.
- macOS `osascript`. It sends the notifications and comes with every Mac.
