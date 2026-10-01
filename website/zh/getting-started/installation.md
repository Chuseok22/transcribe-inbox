# 安装与配置

1. 安装 Python 依赖（会使用 `uv.lock` 中锁定的版本自动创建隔离的 `.venv/`）：
   ```sh
   uv sync
   ```
2. 创建数据库并应用 schema。如果你在用 Docker 运行 PostgreSQL，且本地没有 `psql` 客户端，请在容器内运行 `psql`：
   ```sh
   # 데이터베이스 생성 (컨테이너 이름/사용자는 각자 환경에 맞게 조정)
   docker exec <컨테이너> psql -U <사용자> -d postgres -c "CREATE DATABASE transcribe_inbox"
   # 스키마 적용
   docker exec -i <컨테이너> psql -U <사용자> -d transcribe_inbox < src/transcribe_inbox/db/schema.sql
   ```
   （`<컨테이너>` = 容器名称，`<사용자>` = 数据库用户；注释依次为“创建数据库（容器名称/用户请根据各自环境调整）”和“应用 schema”。）
   （如果本地有 `psql` 客户端，且使用的不是 Docker 中的 PostgreSQL，则等同于 `createdb transcribe_inbox && psql "$DATABASE_URL" -f
   src/transcribe_inbox/db/schema.sql`。）
3. 复制 plist 模板，然后填入实际值 — **绝对不要把真实凭据直接写入被 git 追踪的 `.example` 文件，也不要提交它**；真正的 plist 文件已在 `.gitignore` 中登记，从根本上避免这类失误：
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist
   ```
   打开 `launchd/com.chuseok22.transcribe-inbox.plist` 文件，把所有 `YOUR_USERNAME`/占位符替换为实际值。每个键的含义以及应填的值，请参阅[配置](/zh/reference/configuration)。
4. 安装并启动守护进程：
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. 确认它确实在运行（复制了 plist 并不保证进程一定已经启动 — 如果 plist 中任何一个路径有误，launchd 会悄无声息地失败，不留下任何日志。因为进程本身根本无法启动）：
   ```sh
   launchctl list | grep transcribe-inbox
   ```
   第一列是 PID 表示正在运行，`-` 表示没有运行（第二列是上一次的退出码）。如果没有运行，请检查两个日志文件 — 但要注意，**launchd 启动失败（路径错误的二进制文件等）时日志是完全空的**，因为 Python 进程本身连启动都没能做到，所以什么也写不出来：
   ```sh
   cat ~/Library/Logs/transcribe-inbox.log
   cat ~/Library/Logs/transcribe-inbox.error.log
   ```
   如果两个日志都是空的，而守护进程仍然没有运行，最可能的原因是 plist 中某处的绝对路径有误（`uv`、`whisper-cli`、模型文件等）— 请用 `which`/`ls` 逐一重新确认路径。修改 plist 之后，必须先执行 `launchctl unload`，再重新执行 `launchctl load`；仅仅覆盖文件并不会重新生效。
