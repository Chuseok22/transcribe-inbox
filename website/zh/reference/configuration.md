# 配置

launchd 守护进程从 plist 的 `EnvironmentVariables` 读取配置。安装时复制 `launchd/com.chuseok22.transcribe-inbox.plist`，填入下面的值。

## plist 键

| 键 | 含义 | 说明 |
|---|---|---|
| `ProgramArguments[0]` | `uv` 的绝对路径 | 用 `which uv` 确认。路径因安装方式（Homebrew、官方安装脚本等）而不同，不要假定为 `/opt/homebrew/bin/uv` |
| `DATABASE_URL` | PostgreSQL 连接字符串 | 例：`postgresql://user:password@localhost:5432/transcribe_inbox` |
| `WHISPER_CLI_BINARY` | `whisper-cli` 路径 | 用 `which whisper-cli` 确认 |
| `WHISPER_VAD_MODEL_PATH` | `ggml-silero-v6.2.0.bin` 路径 | 下载到的位置 |
| `WHISPER_ASR_MODEL_PATH` | `ggml-large-v3.bin` 路径 | 下载到的位置 |
| `WHISPER_MLX_MODEL_PATH` | HuggingFace 仓库 ID | 不是文件路径。默认可以使用 `mlx-community/whisper-large-v3-mlx` |
| `HUGGINGFACE_TOKEN` | 创建的 Read 权限令牌 | 只有 `diarize` 模式需要。但路由到该引擎时代码总会读取这个值，所以即使不用 `diarize`，也请填一个占位值 |
| `PATH` | 包含 `uv` 所在目录 | launchd 不继承 shell 的 `PATH`。守护进程调用的所有外部二进制文件都必须能在这里列出的目录中找到，不能假定它们在默认 `PATH` 中 |

## 路径设置（可选）

输入、归档和输出文件夹可以通过环境变量修改。这些值由守护进程读取，而不是 shell。因此必须写进 plist 的 `EnvironmentVariables`，在终端中 `export` 没有效果。

| 用途 | 环境变量 | 默认值 |
|---|---|---|
| 输入（监视）文件夹 | `TRANSCRIBE_INBOX_ROOT` | `~/Transcribe/inbox` |
| 原文件归档文件夹 | `TRANSCRIBE_ARCHIVE_ROOT` | `~/Transcribe/archive` |
| 转写结果输出文件夹 | `OBSIDIAN_TRANSCRIPTS_ROOT` | `~/Obsidian/second-brain/Transcripts` |

- 输出文件夹不必是 Obsidian vault。环境变量名是 `OBSIDIAN_*`，但普通文件夹也可以。结果是 `transcript.json`、`.md`、`.txt`、`.srt` 文件，不用 Obsidian 也能使用。
- 临时工作文件夹（`.staging`）建在输出文件夹下，因此保存结果时的文件夹重命名在同一个卷内完成。
- 归档文件夹可以和输入文件夹在不同的卷上。跨卷移动时通过先复制后删除完成，不是原子操作。
- 不建类别文件夹、直接放在收件箱根目录的文件，类别名称为 `미분류`（未分类）。这个名称写死在代码中，无法更改。
