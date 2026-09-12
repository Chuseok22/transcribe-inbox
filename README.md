# transcribe-inbox

<!-- AUTO-VERSION-SECTION: DO NOT EDIT MANUALLY -->
## Latest Version : v0.0.2 (2026-09-12)

특정 폴더를 감시하다가 새로 들어온 녹음 파일(강의/회의 오디오 **또는 비디오**)을
자동으로 전사(transcription)해서 Obsidian vault에 발행해주는, macOS 전용 로컬
백그라운드 데몬입니다. Apple Silicon GPU 위에서 whisper.cpp/whispermlx 하이브리드
엔진으로 동작하며, 클라우드 API 호출은 전혀 없습니다 — 모든 처리가 로컬에서
이루어집니다. 요약 기능은 없으며, 요약은 사용자가 직접 하도록 남겨둡니다.

## 동작 방식

```
~/Transcribe/inbox/<카테고리>/[모드]/... 에 파일을 넣으면
  → watchdog이 파일을 감지하고, 크기 증가가 멈출 때까지 대기(안정화 확인)
  → PostgreSQL에 작업(job)으로 등록 (idempotent — 같은 내용의 파일은 절대 중복 큐잉되지 않음)
  → 워커가 작업을 하나씩 순차적으로 가져감 (GPU 작업 동시 실행 없음)
  → ffmpeg가 오디오를 16kHz mono WAV로 추출/리샘플링
    (오디오뿐 아니라 비디오 컨테이너에서도 동작 — 아래 "지원하는 입력 포맷" 참고;
    무음 구간을 절대 잘라내지 않으므로, 전사 결과의 타임스탬프는 항상 원본과 일치함)
  → 모드에 따라 엔진으로 라우팅:
      asr / asr-multitrack → whisper.cpp (단일 화자, 또는 사전 분리된 트랙)
      diarize               → whispermlx (다중 화자 회의, 화자 라벨 추가)
  → transcript.json(정본) + .md/.txt/.srt 파일을 Obsidian vault에 발행
  → 원본 파일은 아카이브로 이동, macOS 알림 발송
```

데몬이 재시작되면(크래시, 재부팅 등) 시작 시점에 자체적으로 상태를 정합니다:
처리 도중 멈춰버린 작업은 다시 큐에 등록되거나(원본이 사라졌으면 실패 처리),
전사는 완료됐지만 아카이브로 옮겨지지 못한 작업은 이때 아카이브됩니다.

## 지원하는 입력 포맷

오디오든 비디오든 상관없습니다 — **`ffmpeg`가 오디오를 디코딩할 수 있는 모든
포맷**을 지원합니다. 파이프라인은 파일 확장자를 전혀 검사하지 않고, 그냥
`ffmpeg -i <파일> -ar 16000 -ac 1 <wav>`를 실행할 뿐입니다. 이 명령은 컨테이너
종류와 무관하게 `ffmpeg`가 찾아낸 오디오 스트림을 추출/리샘플링합니다. 직접
검증한 내용: `.m4a`(갤럭시 음성 녹음기 파일)와, 오디오 트랙이 포함된
`.mp4`/`.mov` 계열 비디오 컨테이너 모두 정상 동작 — `ffmpeg`가 오디오 트랙만
추출하고, 파이프라인의 나머지 부분은 비디오 스트림을 아예 보지 않습니다.
`ffmpeg`가 디먹싱조차 못 하는 파일(손상되었거나 지원하지 않는 코덱)은 그 작업
하나만 DB에 명확한 에러와 함께 실패 처리되며, 데몬이 죽거나 다른 작업에
영향을 주지 않습니다.

## 사전 준비물

- 로컬에서 실행 중인 PostgreSQL (작업 큐/상태 저장소 — 전사 내용 자체는
  여기에 저장되지 않고, 작업 상태/메타데이터만 저장됨)
- `ffmpeg`:
  ```sh
  brew install ffmpeg
  ```
- `whisper-cli` (whisper.cpp의 CLI 바이너리) — PyPI 패키지가 **아닙니다**:
  ```sh
  brew install whisper-cpp
  which whisper-cli   # 설치 경로 확인, 아래에서 사용됨
  ```
  이 프로젝트는 아직 whisper.cpp의 특정 git 태그/커밋을 고정해두지 않아서,
  `brew`의 `stable` 버전을 그대로 받게 됩니다 — 알려진 갭입니다.
- whisper.cpp 모델 파일 2개, 개별적으로 다운로드해야 합니다 (HuggingFace
  저장소 전체를 받으면 안 됩니다 — 해당 저장소들은 모든 모델 크기/양자화
  버전을 다 묶어놔서 총 수십 GB에 달합니다):
  - ASR 모델: [`ggml-large-v3.bin`](https://huggingface.co/ggerganov/whisper.cpp/tree/main)
    (이 프로젝트는 정확도를 위해 양자화되지 않은 `large-v3`로 고정되어 있음 —
    수 GB)
  - VAD 모델: [`ggml-silero-v6.2.0.bin`](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin)
    (ASR 모델과 **다른** HuggingFace 저장소입니다 — 1MB 미만)
- `whispermlx` (`diarize` 모드에서 사용) — 아래 `uv sync`로 자동 설치되며,
  별도 설치 단계가 필요 없습니다. 실제 ASR/정렬(alignment)/화자분리 모델은
  직접 다운로드하는 로컬 파일이 **아닙니다** — `whispermlx`가 처음 사용할 때
  HuggingFace에서 자동으로 받아서 `~/.cache/huggingface/` 아래에 캐싱하며,
  `mlx-community/whisper-large-v3-mlx` 같은 모델 이름으로 식별됩니다 (아래
  `WHISPER_MLX_MODEL_PATH`에 실제로 들어가는 값이 바로 이 문자열입니다 —
  이름에 "PATH"가 들어있지만 실제로는 파일 경로가 아니라 HuggingFace 저장소
  ID입니다).
- `diarize` 모드(다중 화자 회의)를 쓸 경우 HuggingFace 액세스 토큰이
  필요합니다 — 화자분리 모델이 gated(승인 필요) 모델이기 때문입니다:
  1. huggingface.co → Settings → Access Tokens에서 **Read** 권한 토큰을
     발급하세요 (Read 권한이면 충분합니다 — 이 프로젝트는 모델을
     다운로드/사용만 하고, 업로드는 전혀 하지 않습니다).
  2. https://huggingface.co/pyannote/speaker-diarization-community-1 에
     방문해서 모델 이용 약관에 동의하세요 — 이 과정 없이는 유효한 토큰이
     있어도 화자분리가 런타임에 실패합니다.
- macOS `osascript` (모든 Mac에 기본 내장되어 있으며, 알림 발송에 사용됨)

## 설치 및 설정

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
   `YOUR_USERNAME`/플레이스홀더를 실제 값으로 바꾸세요:

   | 키 | 의미 | 참고 |
   |---|---|---|
   | `ProgramArguments[0]` | `uv`의 절대 경로 | `which uv`로 확인 — 설치 방식(Homebrew, 공식 설치 스크립트 등)에 따라 달라지므로, `/opt/homebrew/bin/uv`라고 함부로 가정하지 마세요 |
   | `DATABASE_URL` | PostgreSQL 접속 문자열 | 예: `postgresql://user:password@localhost:5432/transcribe_inbox` |
   | `WHISPER_CLI_BINARY` | `whisper-cli` 경로 | `which whisper-cli`로 확인 |
   | `WHISPER_VAD_MODEL_PATH` | `ggml-silero-v6.2.0.bin` 경로 | 다운로드한 위치 |
   | `WHISPER_ASR_MODEL_PATH` | `ggml-large-v3.bin` 경로 | 다운로드한 위치 |
   | `WHISPER_MLX_MODEL_PATH` | HuggingFace 저장소 ID | `mlx-community/whisper-large-v3-mlx`가 무난한 기본값 — 파일 경로가 아님 |
   | `HUGGINGFACE_TOKEN` | 발급받은 Read 권한 토큰 | `diarize` 모드에서만 필요하지만, 코드가 해당 엔진으로 라우팅될 때 무조건 이 값을 읽으므로 `diarize`를 안 쓸 거라면 더미 값이라도 넣어두세요 |
   | `PATH` | `uv`가 있는 디렉터리를 포함 | launchd는 셸의 `PATH`를 **상속하지 않습니다** — 이 데몬이 셸아웃하는 모든 바이너리는 여기 명시된 목록 안에서 찾을 수 있어야 하며, 어떤 기본 `PATH`에 있을 거라 가정하면 안 됩니다 |

   여기 나열된 값들은 전부 셸이 아니라 *데몬 프로세스 자체*가 읽는
   값입니다 — 터미널에서 `export`를 해봐야 아무 영향이 없고, 이 값들은
   오직 이 plist 파일 안에만 존재하면 됩니다.
4. 데몬을 설치하고 시작합니다:
   ```sh
   cp launchd/com.chuseok22.transcribe-inbox.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.chuseok22.transcribe-inbox.plist
   ```
5. 실제로 실행 중인지 확인합니다 (plist를 복사했다고 해서 프로세스가
   반드시 떠 있다는 보장은 없습니다 — 위 경로 중 하나라도 틀리면 launchd는
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

## 인박스 폴더 구조

`~/Transcribe/inbox/<카테고리>/[모드]/<파일 또는 세션>` 형태로 파일을
넣습니다:

- `~/Transcribe/inbox/강의/2주차.m4a` → 카테고리 `강의`, 모드 `asr`
  (기본값 — 단일 화자 녹음이면 모드 폴더 자체를 생략하면 됩니다)
- `~/Transcribe/inbox/회의/diarize/2026-09-08.m4a` → 카테고리 `회의`,
  모드 `diarize` (다중 화자 회의 — whispermlx로 화자 라벨을 추가함)
- `~/Transcribe/inbox/회의/asr-multitrack/2026-09-08/김철수.m4a` (같은
  세션 폴더 안에 다른 화자별 파일들도 함께) → 모드 `asr-multitrack`,
  세션 전체가 하나의 작업으로 처리됨

모드는 오직 폴더 구조로만 결정됩니다 — "이 카테고리는 항상 diarize"처럼
영구적인 기본값을 설정할 방법은 없고, 모든 파일의 모드는 그 파일이 어느
폴더 경로에 놓였는지에 따라 그때그때 결정됩니다. `~/Transcribe/archive/`
(원본 보관용)나 `~/Transcribe/inbox/` 바깥의 다른 폴더는 형제 폴더라 해도
절대 감시 대상이 아닙니다 — 다운로드한 모델(`~/Transcribe/model/` 등)을
포함해 그 외의 것들을 자유롭게 저장해도 안전합니다.

애매한 경로(잘못된 중첩 깊이, 인식되지 않는 모드 이름)는 건너뛰고
로그로 남길 뿐, 절대 추측해서 처리하지 않습니다.

## 사용법

인박스에 파일을 넣으면 자동으로 처리됩니다. 완료되면:

- 전사 결과가 `~/Obsidian/second-brain/Transcripts/<카테고리>/<라벨>/`에
  발행됩니다: `transcript.json`(정본, 세그먼트/단어 단위 타임스탬프와
  해당되는 경우 화자 라벨까지 포함), `transcript.md`, `transcript.txt`,
  `transcript.srt`.
- 원본 파일은 `~/Transcribe/archive/<카테고리>/<모드>/`로 이동합니다.
  같은 이름의 파일이 이미 거기 있다면 새 파일이 절대 덮어쓰지 않고,
  대신 콘텐츠 해시가 붙은 이름으로 저장되므로 원본이 조용히 유실되는
  일은 없습니다.
- 완료 또는 실패 시 macOS 알림이 발송됩니다.

실패한 작업을 재시도하려면 (원본 파일이 아직 존재해야 함):

```sh
transcribe-inbox retry <job-id>
```

작업 상태/이력은 로그 파일이 아니라 PostgreSQL에 저장됩니다 — 특정
작업에 무슨 일이 있었는지 가장 빠르게 확인하는 방법:

```sh
psql "$DATABASE_URL" -c "SELECT id, status, error_message, created_at FROM transcription_job ORDER BY created_at DESC LIMIT 10;"
```

## 알려진 한계

- whisper.cpp가 아직 특정 git 태그/커밋에 고정되어 있지 않습니다 —
  `brew install whisper-cpp`는 업스트림의 `stable` 버전을 그대로
  추종하므로, 이후 업그레이드에서 별다른 경고 없이 동작이 바뀔 수
  있습니다.
- `diarize` 모드는 이 머신에서 실제 녹음을 대상으로 한 end-to-end
  테스트를 아직 거치지 않았습니다 (개발 시점에는 `whisper-cli`/모델이
  설치되어 있지 않았음) — 코드 경로 자체는 실제 `whispermlx` 라이브러리
  소스를 읽어보고 수정했지만, 실제로 의존하기 전에 라이브 스모크 테스트를
  한 번 해보는 게 좋습니다.
- 서로 *다른* 두 녹음이 같은 카테고리+라벨로 귀결되면(같은 작업의 재실행이
  아니라, 진짜 파일명 충돌인 경우) 전사 결과 디렉터리가 덮어써집니다.
  원본 *오디오*는 이런 경우를 방지하도록 되어 있지만(위에서 설명한
  콘텐츠 해시 접미사 처리), 전사 결과 자체는 현재 그렇지 않습니다.
- `HUGGINGFACE_TOKEN`은 현재 (gitignore 처리된) plist 파일에 직접
  넣어야 합니다 — 아직 macOS 키체인이나 별도의 시크릿 파일에서 가져오는
  기능은 지원하지 않습니다.
