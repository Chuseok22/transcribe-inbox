# 설치 및 설정

1. Python 의존성을 설치합니다. `uv.lock`에 고정된 버전으로 격리된 `.venv/`를
   만듭니다.
   ```sh
   uv sync
   ```
2. 데이터베이스를 만들고 스키마를 적용합니다. PostgreSQL을 Docker로 실행 중이고
   로컬에 `psql` 클라이언트가 없다면 컨테이너 안에서 `psql`을 실행하세요.
   ```sh
   # 데이터베이스 생성 (컨테이너 이름/사용자는 각자 환경에 맞게 조정)
   docker exec <컨테이너> psql -U <사용자> -d postgres -c "CREATE DATABASE transcribe_inbox"
   # 스키마 적용
   docker exec -i <컨테이너> psql -U <사용자> -d transcribe_inbox < src/transcribe_inbox/db/schema.sql
   ```
   Docker가 아닌 PostgreSQL을 쓰고 로컬에 `psql` 클라이언트가 있다면 다음
   명령으로 같은 작업을 합니다:
   `createdb transcribe_inbox && psql "$DATABASE_URL" -f src/transcribe_inbox/db/schema.sql`
3. plist 템플릿을 복사한 뒤 실제 값을 채웁니다. **git이 추적하는 `.example`
   파일에는 실제 자격 증명을 넣거나 커밋하지 마세요.** 복사본인 plist 파일은
   이런 실수를 막기 위해 `.gitignore`에 등록되어 있습니다.
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist
   ```
   `launchd/com.chuseok22.transcribe-inbox.plist`를 열어 `YOUR_USERNAME`을
   비롯한 플레이스홀더를 모두 실제 값으로 바꾸세요. 각 키의 의미와 넣을 값은
   [설정](/ko/reference/configuration)에 있습니다.
4. 데몬을 설치하고 시작합니다.
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. 데몬이 실제로 실행 중인지 확인합니다. plist를 복사했다고 프로세스가 떠 있는
   것은 아닙니다. plist 안의 경로가 하나라도 틀리면 프로세스가 시작되지 못해,
   launchd는 로그를 남기지 않고 조용히 실패합니다.
   ```sh
   launchctl list | grep transcribe-inbox
   ```
   첫 번째 컬럼이 PID면 실행 중이고, `-`면 실행 중이 아닙니다. 두 번째 컬럼은
   마지막 종료 코드입니다. 실행 중이 아니면 두 로그 파일을 모두 확인하세요.
   다만 잘못된 바이너리 경로처럼 launchd 단계에서 실행에 실패하면 두 로그는
   비어 있습니다. Python 프로세스가 시작되지 않아 로그를 쓰지 못하기 때문입니다.
   ```sh
   cat ~/Library/Logs/transcribe-inbox.log
   cat ~/Library/Logs/transcribe-inbox.error.log
   ```
   두 로그가 모두 비어 있는데 데몬이 실행되지 않는다면, plist에 적은 절대
   경로(`uv`, `whisper-cli`, 모델 파일 등) 중 하나가 틀렸을 가능성이 가장
   큽니다. `which`나 `ls`로 경로를 하나씩 확인하세요. plist를 수정한 뒤에는
   `launchctl unload`를 실행하고 다시 `launchctl load`를 해야 합니다. 파일만
   덮어써서는 반영되지 않습니다.
