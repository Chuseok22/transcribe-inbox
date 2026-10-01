# 故障排查

## 守护进程没有运行

已经把 plist 复制到 `~/Library/LaunchAgents/` 并执行了 `launchctl load`，但进程不存在。先确认是否在运行。

```sh
launchctl list | grep transcribe-inbox
```

第一列是 PID 表示正在运行，是 `-` 表示没有运行。第二列是上一次的退出码。

- 如果是 `uv` 路径错误这类在 launchd 阶段就启动失败的情况，`~/Library/Logs/transcribe-inbox.log` 和 `~/Library/Logs/transcribe-inbox.error.log` 都是空的。原因是 Python 进程没有启动，无法写日志。
- 如果两个日志都是空的，守护进程又没有运行，最可能的原因是 `ProgramArguments` 中填写的某个绝对路径（`uv` 或项目路径）有误。请用 `which` 或 `ls` 逐一检查。
- 修改 plist 后，需要先执行 `launchctl unload`，再执行 `launchctl load`。只覆盖文件不会生效。
- `whisper-cli` 或模型路径错误不会阻止守护进程启动。守护进程在运行，任务变成 `FAILED`，错误见日志和数据库中记录的错误信息。

安装步骤和各项取值见[安装与配置](/zh/getting-started/installation)和[配置](/zh/reference/configuration)。

## 会话变成 FAILED

`asr-multitrack` 会话变成 `FAILED`，常见原因是会话文件夹中混入了说话人音频以外的文件（`.txt`、`.dat` 等元数据）。会话文件夹中除隐藏文件外的所有文件都会登记为音轨，所以这些文件也会被当作音频解码，然后失败。会话文件夹的正下方只放各说话人的音频文件。音轨起始时间不一致时的注意事项等详细内容，见[支持的模式](/zh/guide/modes)。

## 任务变成 FAILED

任务变成 `FAILED` 后，错误信息会记录到数据库。原文件留在收件箱中，通常不会保存转写结果。如果保存已完成、只是记录完成状态失败，输出文件夹中可能已经有转写结果。失败的任务在守护进程重启后也不会自动重试，请在排除原因后用 `retry` 命令手动重试。查看状态的查询和重试方法见[使用方法](/zh/guide/usage)。
