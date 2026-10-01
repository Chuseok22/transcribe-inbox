# Installation

1. Install the Python dependencies. This creates an isolated `.venv/` with the
   versions pinned in `uv.lock`.
   ```sh
   uv sync
   ```
2. Create the database and apply the schema. If PostgreSQL runs in Docker and you
   have no local `psql` client, run `psql` inside the container.
   ```sh
   # 데이터베이스 생성 (컨테이너 이름/사용자는 각자 환경에 맞게 조정)
   docker exec <컨테이너> psql -U <사용자> -d postgres -c "CREATE DATABASE transcribe_inbox"
   # 스키마 적용
   docker exec -i <컨테이너> psql -U <사용자> -d transcribe_inbox < src/transcribe_inbox/db/schema.sql
   ```
   The comments say: create the database (adjust the container name and user to
   your setup); apply the schema. `<컨테이너>` is the container and `<사용자>` the
   user.
   With a non-Docker PostgreSQL and a local `psql` client, this command does the
   same:
   `createdb transcribe_inbox && psql "$DATABASE_URL" -f src/transcribe_inbox/db/schema.sql`
3. Copy the plist template and fill in the real values. **Do not put real
   credentials in the git-tracked `.example` file or commit them.** The copied
   plist file is listed in `.gitignore` to prevent this.
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist
   ```
   Open `launchd/com.chuseok22.transcribe-inbox.plist` and replace `YOUR_USERNAME`
   and every other placeholder with real values. [Configuration](/reference/configuration)
   explains each key and what to put in it.
4. Install and start the daemon.
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. Check that the daemon is running. Copying the plist does not mean the process
   is up. If the `uv` path or the project path in `ProgramArguments` is wrong, the
   process cannot start and launchd fails without writing a log. A wrong
   `whisper-cli` or model path does not stop the daemon from starting. The job
   ends as FAILED instead, with the error in the log and the database.
   ```sh
   launchctl list | grep transcribe-inbox
   ```
   A PID in the first column means it is running. `-` means it is not. The second
   column is the last exit code. If it is not running, check both log files. When
   launchd itself fails to start the process, for example because of a wrong
   `uv` path, both logs are empty, because the Python process never started and
   could not write anything.
   ```sh
   cat ~/Library/Logs/transcribe-inbox.log
   cat ~/Library/Logs/transcribe-inbox.error.log
   ```
   If both logs are empty and the daemon is not running, the most likely cause is
   a wrong absolute path in `ProgramArguments` (`uv` or the project path). Check
   each path with `which` or `ls`. After you edit the plist, run
   `launchctl unload` and then `launchctl load` again. Overwriting the file alone
   does not apply the change. A wrong `whisper-cli` or model path shows up as
   FAILED jobs instead, see [Troubleshooting](/help/troubleshooting).
