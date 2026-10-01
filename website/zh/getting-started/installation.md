# 安装与配置

1. 安装 Python 依赖。会按 `uv.lock` 中锁定的版本创建隔离的 `.venv/`。
   ```sh
   uv sync
   ```
2. 创建数据库并应用 schema。如果 PostgreSQL 运行在 Docker 中，而本地没有 `psql` 客户端，请在容器内运行 `psql`。
   ```sh
   # 데이터베이스 생성 (컨테이너 이름/사용자는 각자 환경에 맞게 조정)
   docker exec <컨테이너> psql -U <사용자> -d postgres -c "CREATE DATABASE transcribe_inbox"
   # 스키마 적용
   docker exec -i <컨테이너> psql -U <사용자> -d transcribe_inbox < src/transcribe_inbox/db/schema.sql
   ```
   `<컨테이너>` 是容器名称，`<사용자>` 是数据库用户。两行注释分别意为“创建数据库（容器名称和用户请按自己的环境调整）”和“应用 schema”。
   如果使用的不是 Docker 中的 PostgreSQL，并且本地有 `psql` 客户端，可以用下面的命令完成同样的操作：
   `createdb transcribe_inbox && psql "$DATABASE_URL" -f src/transcribe_inbox/db/schema.sql`
3. 复制 plist 模板，然后填入实际值。**不要把真实凭据写进 git 追踪的 `.example` 文件，也不要提交它。** 复制出来的 plist 文件已登记在 `.gitignore` 中，以防出现这类失误。
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist
   ```
   打开 `launchd/com.chuseok22.transcribe-inbox.plist`，把 `YOUR_USERNAME` 等所有占位符替换为实际值。各个键的含义和应填的值见[配置](/zh/reference/configuration)。
4. 安装并启动守护进程。
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. 确认守护进程确实在运行。复制了 plist 不代表进程已经启动。plist 中只要有一个路径写错，进程就无法启动，launchd 会在不留日志的情况下失败。
   ```sh
   launchctl list | grep transcribe-inbox
   ```
   第一列是 PID 表示正在运行，是 `-` 表示没有运行。第二列是上一次的退出码。如果没有运行，请检查两个日志文件。不过，如果是二进制路径错误这类在 launchd 阶段就启动失败的情况，两个日志都是空的，因为 Python 进程没有启动，无法写日志。
   ```sh
   cat ~/Library/Logs/transcribe-inbox.log
   cat ~/Library/Logs/transcribe-inbox.error.log
   ```
   如果两个日志都是空的，守护进程又没有运行，最可能的原因是 plist 中填写的某个绝对路径（`uv`、`whisper-cli`、模型文件等）有误。请用 `which` 或 `ls` 逐一检查路径。修改 plist 后，需要先执行 `launchctl unload`，再执行 `launchctl load`。只覆盖文件不会生效。
