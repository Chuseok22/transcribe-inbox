# Installation

1. Install the Python dependencies (this automatically creates an isolated `.venv/` using the versions pinned in `uv.lock`):
   ```sh
   uv sync
   ```
2. Create the database and apply the schema. If you run PostgreSQL in Docker and have no local `psql` client, run `psql` inside the container:
   ```sh
   # 데이터베이스 생성 (컨테이너 이름/사용자는 각자 환경에 맞게 조정)
   docker exec <컨테이너> psql -U <사용자> -d postgres -c "CREATE DATABASE transcribe_inbox"
   # 스키마 적용
   docker exec -i <컨테이너> psql -U <사용자> -d transcribe_inbox < src/transcribe_inbox/db/schema.sql
   ```
   (Comments in the block: create the database — adjust the container name/user to your environment; apply the schema. `<컨테이너>` is the container, `<사용자>` the user.)
   (If you have a local `psql` client and use a non-Docker PostgreSQL, this is equivalent to `createdb transcribe_inbox && psql "$DATABASE_URL" -f
   src/transcribe_inbox/db/schema.sql`.)
3. Copy the plist template, then fill in the real values — **never put real credentials directly into the git-tracked `.example` file or commit them**; the real plist file is registered in `.gitignore` so that this mistake can't happen in the first place:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist
   ```
   Open `launchd/com.chuseok22.transcribe-inbox.plist` and replace every `YOUR_USERNAME`/placeholder with a real value. See [Configuration](/reference/configuration) for what each key means and what to fill in.
4. Install and start the daemon:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. Verify that it is actually running (copying the plist does not guarantee that the process is up — if any path in the plist is wrong, launchd fails silently without logging anything, because the process itself never gets to start):
   ```sh
   launchctl list | grep transcribe-inbox
   ```
   If the first column is a PID, it is running; if it is `-`, it is not running (the second column is the last exit code). If it is not running, check both log files — but note that **a launchd launch failure (such as a wrong binary path) leaves the logs completely empty**, because the Python process could not even start and so had nothing to write:
   ```sh
   cat ~/Library/Logs/transcribe-inbox.log
   cat ~/Library/Logs/transcribe-inbox.error.log
   ```
   If both logs are empty and the daemon still isn't running, the most likely cause is a wrong absolute path somewhere in the plist (`uv`, `whisper-cli`, the model files, etc.) — re-check the paths one by one with `which`/`ls`. After editing the plist, you must run `launchctl unload` and then `launchctl load` again; just overwriting the file does not re-apply it.
