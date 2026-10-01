# 前置条件

::: info
本文档由 AI 翻译自韩文原文，欢迎通过 GitHub Issue 反馈翻译错误。
:::

## 支持的输入格式

只要 `ffmpeg` 能解码其中的音频，音频和视频都支持。流水线不检查文件扩展名，而是运行 `ffmpeg -i <文件> -ar 16000 -ac 1 <wav>`。这条命令不管容器是什么类型，都会提取 `ffmpeg` 找到的音频流并重新采样。

已实际验证过的格式有 `.m4a`（Galaxy 录音机文件），以及带音轨的 `.mp4`/`.mov` 系列视频容器。处理视频时，`ffmpeg` 只提取音轨，后续步骤不会处理视频流。

文件已损坏或编解码器不受支持，导致 `ffmpeg` 无法解复用时，只有该任务会被标记为失败，错误会记录到数据库。守护进程继续运行，其他任务也不受影响。

## 所需环境

- 在本地运行的 PostgreSQL，用作任务队列和状态存储。转写内容不存放在这里，只保存任务状态和元数据。
- `ffmpeg`：
  ```sh
  brew install ffmpeg
  ```
- `whisper-cli`（whisper.cpp 的 CLI 二进制文件）。它不是 PyPI 包。
  ```sh
  brew install whisper-cpp
  which whisper-cli   # 설치 경로 확인, 아래에서 사용됨
  ```
  代码块中的注释意为“确认安装路径，下文会用到”。本项目还没有把 whisper.cpp 固定到特定的 git 标签或提交，因此直接安装 `brew` 的 `stable` 版本。这是一项已知限制。
- 2 个 whisper.cpp 模型文件。请逐个下载，不要下载整个 HuggingFace 仓库。这些仓库包含所有尺寸和量化版本的模型，加起来有几十 GB。
  - ASR 模型：[`ggml-large-v3.bin`](https://huggingface.co/ggerganov/whisper.cpp/tree/main)。为了保证准确率，固定使用未量化的 `large-v3`，大小为数 GB。
  - VAD 模型：[`ggml-silero-v6.2.0.bin`](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin)。它与 ASR 模型在不同的 HuggingFace 仓库中，大小不到 1MB。
- `whispermlx`（`diarize` 模式使用）。执行[安装与配置](/zh/getting-started/installation)中的 `uv sync` 时会一并安装，不需要单独的安装步骤。ASR、对齐（alignment）和说话人分离模型不是需要你手动下载的本地文件。`whispermlx` 首次使用时会从 HuggingFace 下载，缓存到 `~/.cache/huggingface/` 下，并用 `mlx-community/whisper-large-v3-mlx` 这样的模型名称区分。[配置](/zh/reference/configuration)中 `WHISPER_MLX_MODEL_PATH` 填的就是这个字符串。名称里虽然有 "PATH"，但它的值是 HuggingFace 仓库 ID，不是文件路径。
- 使用 `diarize` 模式（多说话人会议）时需要 HuggingFace 访问令牌，因为说话人分离模型是需要批准才能使用的 gated 模型。
  1. 在 huggingface.co → Settings → Access Tokens 中创建一个 Read 权限的令牌。本项目只下载和使用模型，不会上传，所以 Read 权限就够了。
  2. 打开 https://huggingface.co/pyannote/speaker-diarization-community-1 ，同意模型的使用条款。如果没有同意，即使令牌有效，说话人分离也会在运行时失败。
- macOS `osascript`，用于发送通知。所有 Mac 都自带。
