# transcribe-inbox

[English](README.md) | [한국어](README.ko.md) | **简体中文**

![Release](https://img.shields.io/github/v/release/Chuseok22/transcribe-inbox)
![License](https://img.shields.io/github/license/Chuseok22/transcribe-inbox)
![Platform](https://img.shields.io/badge/platform-macOS%20(Apple%20Silicon)-lightgrey)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://chuseok22.github.io/transcribe-inbox/zh/)

把录音文件放进文件夹，即可在 Apple Silicon 上本地转写，并发布到笔记中。

> **仅支持 macOS + Apple Silicon**。不支持 Linux、Windows 和 Intel Mac。

> 本文档由 AI 翻译自韩文原文，欢迎通过 Issue 反馈翻译错误。

<!-- 演示 GIF 位置：由用户提供后插入 -->

这是一个本地后台守护进程：它监视指定文件夹，自动转写新放入的录音文件（音频或视频），并发布到 Obsidian vault（或普通文件夹）。它采用 whisper.cpp / whispermlx 混合引擎，不调用任何云端 API。

只要 `ffmpeg` 能解码音频，无论是音频还是视频文件都可以。流水线不检查文件扩展名，而是用 `ffmpeg` 仅提取音频流，并且不会裁剪静音片段，因此转写结果的时间戳始终与原文件一致。`ffmpeg` 无法打开的文件只会让该任务失败，不会影响守护进程和其他任务。

## 主要特性

- **完全本地，隐私优先**：所有处理都在你的 Mac 上完成，不调用云端 API。
- **文件夹结构即配置**：文件放在哪一层文件夹，就决定了类别和模式。没有配置文件，也没有文件名规则。
- **3 种模式**：单一说话人的 `asr`、合并按说话人分开的音轨的 `asr-multitrack`、区分同一文件中多位说话人的 `diarize`。
- **幂等入队与状态恢复**：通过内容哈希判断，内容相同的文件不会重复登记；守护进程重启后，会自行确定被中断任务的状态。
- **不做摘要，原文发布**：结果以 `transcript.json`（正本）、`.md`、`.txt`、`.srt` 输出。摘要由你自己完成。
- **无需 Obsidian 也能使用**：结果是写入普通文件夹的 Markdown、JSON、SRT 文件，任何工具都能打开。

## 工作流程

文件进入收件箱后，按以下顺序处理。任务一次只顺序执行一个。

```mermaid
flowchart LR
  A["将文件放入 ~/Transcribe/inbox/"] --> B["watchdog：等待文件大小稳定"]
  B --> C[("PostgreSQL 任务队列")]
  C --> D["Worker：一次处理一个任务"]
  D --> E["ffmpeg：16kHz mono WAV"]
  E --> F{"模式"}
  F -->|"asr / asr-multitrack"| G["whisper.cpp"]
  F -->|"diarize"| H["whispermlx"]
  G --> I["发布 transcript.json · .md · .txt · .srt"]
  H --> I
  I --> J["原文件归档 + macOS 通知"]
```

## 环境要求

- macOS + Apple Silicon
- 在本地运行的 PostgreSQL（任务队列与状态存储）
- `ffmpeg`
- `whisper-cli`（whisper.cpp）和 2 个模型文件（ASR 模型 `ggml-large-v3.bin`，VAD 模型 `ggml-silero-v6.2.0.bin`）
- `uv`（安装 Python 依赖）
- 仅 `diarize` 模式需要：HuggingFace **Read** 令牌，并同意说话人分离模型的使用条款

各项的安装方法请参阅[前置准备](https://chuseok22.github.io/transcribe-inbox/zh/getting-started/prerequisites)和[安装指南](https://chuseok22.github.io/transcribe-inbox/zh/getting-started/installation)。

## 快速开始

这是首次安装的最少步骤。安装完成后，只需把录音文件放到 `~/Transcribe/inbox/` 下即可。

需要先创建 PostgreSQL 数据库并应用 schema，再下载 2 个模型——参见[安装指南](https://chuseok22.github.io/transcribe-inbox/zh/getting-started/installation)。

```sh
brew install ffmpeg whisper-cpp
uv sync   # 应用 DB schema、下载模型请参阅安装指南
cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist   # 请填入相应的值
cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
```

必须在 plist 中填入 `uv`、`whisper-cli`、模型文件的绝对路径以及 `DATABASE_URL` 等，守护进程才能运行。详细设置请参阅[文档](https://chuseok22.github.io/transcribe-inbox/zh/)。

## 文档

完整文档见 [https://chuseok22.github.io/transcribe-inbox/zh/](https://chuseok22.github.io/transcribe-inbox/zh/)。

- **入门**：[前置准备](https://chuseok22.github.io/transcribe-inbox/zh/getting-started/prerequisites)、[安装](https://chuseok22.github.io/transcribe-inbox/zh/getting-started/installation)
- **指南**：[收件箱文件夹结构](https://chuseok22.github.io/transcribe-inbox/zh/guide/inbox-layout)、[模式](https://chuseok22.github.io/transcribe-inbox/zh/guide/modes)、[使用方法](https://chuseok22.github.io/transcribe-inbox/zh/guide/usage)
- **参考**：[配置](https://chuseok22.github.io/transcribe-inbox/zh/reference/configuration)、[输出格式](https://chuseok22.github.io/transcribe-inbox/zh/reference/output)
- **故障排查**：[故障排查](https://chuseok22.github.io/transcribe-inbox/zh/help/troubleshooting)、[已知限制](https://chuseok22.github.io/transcribe-inbox/zh/help/known-limitations)

## 已知限制

目前已知的限制如下。

- whisper.cpp 没有固定到特定的 git 标签/提交，因此通过 `brew install whisper-cpp` 获取的 `stable` 版本一旦变化，行为可能随之改变。
- `diarize` 模式尚未针对真实录音做过端到端测试。在依赖它之前，请先做一次冒烟测试。
- 如果两段不同的录音归入相同的类别和标签，转写结果目录会被覆盖。原始音频通过内容哈希后缀得到保护，但转写结果目前还没有这种保护。
- `HUGGINGFACE_TOKEN` 必须直接写入（已被 gitignore 忽略的）plist 文件，目前不支持钥匙串或单独的密钥文件。
- 直接放在收件箱根目录的文件，其类别名称 `미분류`（未分类）在代码中是固定的，无法更改。
- 转写语言目前固定为韩语（`ko`），暂不支持配置其他语言。

详情请参阅[已知限制](https://chuseok22.github.io/transcribe-inbox/zh/help/known-limitations)页面。

## 参与贡献

贡献方式请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。修改 README 时，以韩文（`README.ko.md`）为原文，并同步更新英文和中文译本。

## 许可证

MIT — [LICENSE](LICENSE)
