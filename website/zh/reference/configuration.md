# 配置

launchd 守护进程从 plist 的 `EnvironmentVariables` 中读取配置。安装过程中会复制 `launchd/com.chuseok22.transcribe-inbox.plist` 并填入下面这些值。

## plist 键

| 键 | 含义 | 备注 |
|---|---|---|
| `ProgramArguments[0]` | `uv` 的绝对路径 | 用 `which uv` 确认 — 会因安装方式（Homebrew、官方安装脚本等）而不同，所以不要随意假定就是 `/opt/homebrew/bin/uv` |
| `DATABASE_URL` | PostgreSQL 连接字符串 | 例：`postgresql://user:password@localhost:5432/transcribe_inbox` |
| `WHISPER_CLI_BINARY` | `whisper-cli` 路径 | 用 `which whisper-cli` 确认 |
| `WHISPER_VAD_MODEL_PATH` | `ggml-silero-v6.2.0.bin` 路径 | 下载到的位置 |
| `WHISPER_ASR_MODEL_PATH` | `ggml-large-v3.bin` 路径 | 下载到的位置 |
| `WHISPER_MLX_MODEL_PATH` | HuggingFace 仓库 ID | `mlx-community/whisper-large-v3-mlx` 是比较稳妥的默认值 — 不是文件路径 |
| `HUGGINGFACE_TOKEN` | 签发的 Read 权限令牌 | 只有 `diarize` 模式需要，但当代码路由到该引擎时一定会读取这个值，所以如果不打算使用 `diarize`，也请填入一个占位值 |
| `PATH` | 包含 `uv` 所在的目录 | launchd **不会继承** shell 的 `PATH` — 这个守护进程调用的所有二进制文件都必须能在这里列出的目录中找到，不能假定它们存在于某个默认 `PATH` 中 |

## 路径设置（可选）

输入、归档、输出文件夹可以通过环境变量更改。这些值由**守护进程**而不是 shell 读取，因此必须写入 plist 的 `EnvironmentVariables`，在终端中使用 `export` 不起作用。

| 用途 | 环境变量 | 默认值 |
|---|---|---|
| 输入（监视）文件夹 | `TRANSCRIBE_INBOX_ROOT` | `~/Transcribe/inbox` |
| 原始文件归档文件夹 | `TRANSCRIBE_ARCHIVE_ROOT` | `~/Transcribe/archive` |
| 转写结果输出文件夹 | `OBSIDIAN_TRANSCRIPTS_ROOT` | `~/Obsidian/second-brain/Transcripts` |

- 输出文件夹不必是 Obsidian vault。只是名字叫 `OBSIDIAN_*`，普通文件夹也可以。结果是 `transcript.json`、`.md`、`.txt`、`.srt` 文件，所以没有 Obsidian 也能使用。
- 临时工作文件夹（`.staging`）会创建在输出文件夹之下，因此发布时的文件夹重命名发生在同一个卷上。
- 原始文件归档文件夹可以与输入文件夹位于不同的卷。移动是通过先复制再删除来处理的，不是原子操作。
- 不带类别、直接放在收件箱根目录的文件所使用的类别名称 `미분류`（未分类）在代码中是固定的，无法更改。
