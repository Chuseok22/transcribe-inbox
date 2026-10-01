# 설치 및 설정

1. Python 의존성 설치 (`uv.lock`에 고정된 버전으로 격리된 `.venv/`를
   자동 생성합니다):
   ```sh
   uv sync
   ```
2. 데이터베이스를 생성하고 스키마를 적용합니다. Docker로 PostgreSQL을
   실행 중이고 로컬에 `psql` 클라이언트가 없다면, 컨테이너 안에서 `psql`을
   실행하세요:
   ```sh
   # 데이터베이스 생성 (컨테이너 이름/사용자는 각자 환경에 맞게 조정)
   docker exec <컨테이너> psql -U <사용자> -d postgres -c "CREATE DATABASE transcribe_inbox"
   # 스키마 적용
   docker exec -i <컨테이너> psql -U <사용자> -d transcribe_inbox < src/transcribe_inbox/db/schema.sql
   ```
   (로컬에 `psql` 클라이언트가 있고 Docker가 아닌 PostgreSQL을 쓴다면,
   `createdb transcribe_inbox && psql "$DATABASE_URL" -f
   src/transcribe_inbox/db/schema.sql`와 동일합니다.)
3. plist 템플릿을 복사한 뒤 실제 값을 채워 넣으세요 — **git에 추적되는
   `.example` 파일에는 절대 실제 자격증명을 직접 넣거나 커밋하지 마세요**;
   진짜 plist 파일은 이런 실수가 애초에 일어나지 않도록 `.gitignore`에
   등록되어 있습니다:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist.example launchd/com.chuseok22.transcribe-inbox.plist
   ```
   `launchd/com.chuseok22.transcribe-inbox.plist` 파일을 열어서 모든
   `YOUR_USERNAME`/플레이스홀더를 실제 값으로 바꾸세요.
   각 키의 의미와 채울 값은 [설정](/ko/reference/configuration)을 참고하세요.
4. 데몬을 설치하고 시작합니다:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. 실제로 실행 중인지 확인합니다 (plist를 복사했다고 해서 프로세스가
   반드시 떠 있다는 보장은 없습니다 — plist 안의 경로 중 하나라도 틀리면 launchd는
   아무것도 로그로 남기지 않은 채 조용히 실패합니다. 프로세스 자체가 아예
   시작되지 못하기 때문입니다):
   ```sh
   launchctl list | grep transcribe-inbox
   ```
   첫 번째 컬럼이 PID면 실행 중, `-`면 실행 중이 아닙니다 (두 번째 컬럼은
   마지막 종료 코드). 실행 중이 아니라면 두 로그 파일을 모두 확인하세요 —
   단, **launchd 실행 실패(잘못된 바이너리 경로 등)는 로그가 완전히
   비어있습니다**, Python 프로세스 자체가 시작조차 못 해서 아무것도 쓸 수
   없기 때문입니다:
   ```sh
   cat ~/Library/Logs/transcribe-inbox.log
   cat ~/Library/Logs/transcribe-inbox.error.log
   ```
   두 로그가 모두 비어 있는데도 데몬이 실행되지 않는다면, plist 안 어딘가의
   절대 경로가 틀렸을 가능성이 가장 큽니다 (`uv`, `whisper-cli`, 모델
   파일 등) — `which`/`ls`로 경로를 하나씩 다시 확인하세요. plist를 수정한
   뒤에는 반드시 `launchctl unload` 후 다시 `launchctl load`를 해야
   합니다; 파일만 덮어쓰는 것으로는 재적용되지 않습니다.
