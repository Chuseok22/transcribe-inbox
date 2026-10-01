# 前置条件

::: info
本文档由 AI 翻译自韩文原文，欢迎通过 GitHub Issue 反馈翻译错误。
:::

## 支持的输入格式

无论是音频还是视频都可以 — 支持 **`ffmpeg` 能够解码音频的所有格式**。流水线完全不检查文件扩展名，只是运行 `ffmpeg -i <文件> -ar 16000 -ac 1 <wav>`。无论容器类型如何，该命令都会提取 `ffmpeg` 找到的音频流并重新采样。已亲自验证的内容：`.m4a`（Galaxy 录音机文件）以及包含音轨的 `.mp4`/`.mov` 系列视频容器均能正常工作 — `ffmpeg` 只提取音轨，流水线的其余部分完全不会接触视频流。对于 `ffmpeg` 连解复用都无法完成的文件（已损坏或使用不支持的编解码器），只有该任务会在数据库中带着明确的错误信息被标记为失败，守护进程不会崩溃，也不会影响其他任务。

## 所需条件

- 在本地运行的 PostgreSQL（任务队列/状态存储 — 转写内容本身不会存储在这里，只保存任务状态/元数据）
- `ffmpeg`：
  ```sh
  brew install ffmpeg
  ```
- `whisper-cli`（whisper.cpp 的 CLI 二进制文件）— **不是** PyPI 包：
  ```sh
  brew install whisper-cpp
  which whisper-cli   # 설치 경로 확인, 아래에서 사용됨
  ```
  （代码块中的注释：确认安装路径，下文会用到。）
  本项目尚未固定 whisper.cpp 的特定 git 标签/提交，因此会直接获取 `brew` 的 `stable` 版本 — 这是已知的缺口。
- 2 个 whisper.cpp 模型文件，需要分别下载（不要下载整个 HuggingFace 仓库 — 这些仓库把所有模型尺寸/量化版本都打包在一起，总共达数十 GB）：
  - ASR 模型：[`ggml-large-v3.bin`](https://huggingface.co/ggerganov/whisper.cpp/tree/main)
    （为了保证准确率，本项目固定使用未量化的 `large-v3` — 数 GB）
  - VAD 模型：[`ggml-silero-v6.2.0.bin`](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin)
    （与 ASR 模型位于**不同的** HuggingFace 仓库 — 不到 1MB）
- `whispermlx`（用于 `diarize` 模式）— 会通过[安装与配置](/zh/getting-started/installation)中的 `uv sync` 自动安装，无需单独的安装步骤。实际的 ASR/对齐（alignment）/说话人分离模型**不是**需要你手动下载的本地文件 — `whispermlx` 会在首次使用时从 HuggingFace 自动下载，并缓存在 `~/.cache/huggingface/` 下，通过 `mlx-community/whisper-large-v3-mlx` 这样的模型名称来标识（[配置](/zh/reference/configuration)中 `WHISPER_MLX_MODEL_PATH` 实际填入的值就是这个字符串 — 名称里虽然带有 "PATH"，但它实际上不是文件路径，而是 HuggingFace 仓库 ID）。
- 如果使用 `diarize` 模式（多说话人会议），需要 HuggingFace 访问令牌 — 因为说话人分离模型是 gated（需要批准）模型：
  1. 在 huggingface.co → Settings → Access Tokens 中签发一个 **Read** 权限的令牌（Read 权限就足够了 — 本项目只下载/使用模型，完全不会上传）。
  2. 访问 https://huggingface.co/pyannote/speaker-diarization-community-1 并同意模型使用条款 — 如果没有这一步，即使有有效的令牌，说话人分离在运行时也会失败。
- macOS `osascript`（所有 Mac 均内置，用于发送通知）
