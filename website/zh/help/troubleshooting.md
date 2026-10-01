# 故障排查

## 守护进程没有启动

这是指已将 plist 复制到 `~/Library/LaunchAgents/` 并执行了 `launchctl load`，但进程仍没有运行的情况。首先确认是否在运行：

```sh
launchctl list | grep transcribe-inbox
```

第一列是 PID 表示正在运行，`-` 表示没有运行（第二列是上一次的退出码）。

- launchd 启动失败（路径错误的二进制文件等）时，`~/Library/Logs/transcribe-inbox.log` 和 `~/Library/Logs/transcribe-inbox.error.log` **都是空的。** 因为 Python 进程本身无法启动，所以什么也写不出来。
- 如果两个日志都是空的，而守护进程仍然没有运行，最可能的原因是 plist 中的绝对路径（`uv`、`whisper-cli`、模型文件等）有误。请用 `which`/`ls` 逐一重新确认。
- 修改 plist 之后，必须先执行 `launchctl unload`，再重新执行 `launchctl load`。仅仅覆盖文件并不会重新生效。

详细的安装步骤和各个值，请参阅[安装与配置](/zh/getting-started/installation)和[配置](/zh/reference/configuration)。

## 会话变成 FAILED

`asr-multitrack` 会话变成 `FAILED` 的常见原因，是会话文件夹中混入了各说话人音频之外的文件（`.txt`、`.dat` 等元数据）。会话文件夹内所有非隐藏文件都会被登记为音轨，并在尝试音频解码时失败。请只在会话文件夹的正下方放置各说话人的音频文件。包括音轨起始时间不一致时的注意事项在内的详细内容，请参阅[支持的模式](/zh/guide/modes)。

## 任务变成了 FAILED

任务变成 `FAILED` 后，错误信息会记录到数据库，原始文件会原样保留在收件箱中，转写结果不会被发布。失败的任务即使重启守护进程也不会自动重试，因此需要在解决原因之后，通过 `retry` 命令手动重新尝试。查看状态的查询和重试方法，请参阅[使用方法](/zh/guide/usage)。
