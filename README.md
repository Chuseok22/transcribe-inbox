# transcribe-inbox

<!-- AUTO-VERSION-SECTION: DO NOT EDIT MANUALLY -->
## Latest Version : v0.1.1 (2026-09-12)

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

감시 대상은 `~/Transcribe/inbox/` 한 곳뿐입니다. 이 폴더 아래 **어느 깊이에
파일을 놓느냐**가 그대로 카테고리와 모드를 결정합니다 — 설정 파일도, 파일명
규칙도 없습니다.

`~/Transcribe/inbox/`부터 센 경로 구성 요소의 개수만 보면 됩니다:

| 인박스 기준 상대 경로 | 카테고리 | 모드 | 작업 단위 |
|---|---|---|---|
| `<파일>` | `미분류` | `asr` | 그 파일 |
| `<카테고리>/<파일>` | `<카테고리>` | `asr` | 그 파일 |
| `<카테고리>/asr/<파일>` | `<카테고리>` | `asr` | 그 파일 |
| `<카테고리>/diarize/<파일>` | `<카테고리>` | `diarize` | 그 파일 |
| `<카테고리>/asr-multitrack/<세션>/<파일>` | `<카테고리>` | `asr-multitrack` | `<세션>` 폴더 전체 |

말로 풀면 규칙은 네 줄입니다:

- **카테고리**는 인박스 바로 아래 첫 번째 폴더 이름입니다. 이름은 자유이고
  (`강의`, `회의`, `캡스톤` 등 한글 그대로 가능), 새 카테고리를 쓰려고
  어딘가에 등록할 필요는 없습니다 — 폴더만 만들면 됩니다.
- **카테고리 폴더 없이** 인박스 루트에 파일을 그냥 떨어뜨려도 정상 동작하며,
  카테고리는 `미분류`, 모드는 `asr`이 됩니다. 전사 결과는
  `~/Obsidian/second-brain/Transcripts/미분류/` 아래에, 원본은
  `~/Transcribe/archive/미분류/asr/`로 갑니다.
- **모드 폴더**는 두 번째 폴더이고 생략할 수 있습니다. 생략하면 `asr`입니다.
  이름은 `asr`, `asr-multitrack`, `diarize` 셋 중 하나와 정확히 일치해야
  합니다 — `ASR`, `multitrack`처럼 대소문자가 다르거나 변형된 이름은 모드로
  인식되지 않습니다.
- `asr-multitrack`만 한 단계 더 깊습니다. 모드 폴더 아래에 **세션 폴더**를
  반드시 하나 두고 화자별 파일을 그 안에 바로 넣습니다. 이때 작업 단위는
  개별 파일이 아니라 세션 폴더 전체입니다.

위 다섯 가지 형태 중 어디에도 해당하지 않는 경로는 전부 **애매한 경로**로
보고 건너뛴 뒤 로그만 남깁니다 — 절대 추측해서 처리하지 않습니다. 실제로
걸리는 경우들:

```
~/Transcribe/inbox/강의/3장/2주차.m4a                              # 두 번째 폴더가 모드 이름이 아님
~/Transcribe/inbox/회의/asr-multitrack/회의록.m4a                  # 세션 폴더 없이 파일을 바로 넣음
~/Transcribe/inbox/회의/asr-multitrack/2026-09-08/원본/김철수.m4a  # 세션 폴더 아래에 또 폴더
```

모드는 오직 폴더 구조로만 결정됩니다 — "이 카테고리는 항상 diarize"처럼
영구적인 기본값을 설정할 방법은 없고, 모든 파일의 모드는 그 파일이 어느
폴더 경로에 놓였는지에 따라 그때그때 결정됩니다. `~/Transcribe/archive/`
(원본 보관용)나 `~/Transcribe/inbox/` 바깥의 다른 폴더는 형제 폴더라 해도
절대 감시 대상이 아닙니다 — 다운로드한 모델(`~/Transcribe/model/` 등)을
포함해 그 외의 것들을 자유롭게 저장해도 안전합니다. 이름이 `.`으로 시작하는
숨김 파일은 어디에 있든 전부 무시됩니다.

## 지원하는 모드

모드는 정확히 3개뿐입니다.

| 모드 | 언제 쓰나 | 엔진 | 화자 라벨 |
|---|---|---|---|
| `asr` (기본값) | 화자가 한 명인 녹음 — 강의, 혼자 말한 메모 | whisper.cpp | 없음 |
| `asr-multitrack` | 화자별로 **이미 파일이 나뉘어 있는** 녹음 — 참석자가 각자 자기 기기로 녹음한 회의 | whisper.cpp (트랙마다 한 번씩) | 트랙 파일 이름(확장자 제외) |
| `diarize` | 한 파일 안에 여러 화자가 **섞여 있는** 녹음 — 마이크 하나로 녹음한 회의 | whispermlx | 화자분리 모델이 붙인 익명 라벨 |

`asr`과 `diarize`의 차이는 전사 품질이 아니라 화자 구분 여부입니다. 화자를
나눌 필요가 없다면 `diarize`를 쓸 이유가 없습니다 — 정렬(alignment)과
화자분리 단계가 추가로 돌기 때문에 상당히 더 오래 걸립니다.

화자별 파일을 이미 갖고 있다면 `diarize`보다 `asr-multitrack`이 낫습니다.
화자분리는 추론이라 틀릴 수 있지만, `asr-multitrack`은 어느 파일이 누구
것인지 이미 확정되어 있어서 화자 라벨이 틀릴 여지가 없습니다.

### `asr` — 단일 화자 (기본값)

모드 폴더를 생략하면 됩니다:

```
~/Transcribe/inbox/
└── 강의/
    └── 2주차.m4a
```

- 전사 결과: `~/Obsidian/second-brain/Transcripts/강의/2주차/`
- 아카이브: `~/Transcribe/archive/강의/asr/2주차.m4a`

`~/Transcribe/inbox/강의/asr/2주차.m4a`처럼 모드를 명시해도 결과는 완전히
동일합니다.

### `diarize` — 여러 화자가 한 파일에 섞인 회의

```
~/Transcribe/inbox/
└── 회의/
    └── diarize/
        └── 2026-09-08.m4a
```

- 전사 결과: `~/Obsidian/second-brain/Transcripts/회의/2026-09-08/`
- 아카이브: `~/Transcribe/archive/회의/diarize/2026-09-08.m4a`
- 화자 라벨은 화자분리 모델이 자동으로 붙이는 익명 라벨입니다 — 실제 사람
  이름이 아니며, 누가 누구인지는 전사본을 보고 직접 대응시켜야 합니다.
- 이 모드만 `HUGGINGFACE_TOKEN`과 모델 약관 동의가 필요합니다 (위 "사전
  준비물" 참고).

### `asr-multitrack` — 화자별로 파일이 나뉜 회의

모드 폴더 아래에 세션 폴더를 하나 만들고, 그 안에 화자별 파일을 넣습니다:

```
~/Transcribe/inbox/
└── 회의/
    └── asr-multitrack/
        └── 2026-09-08/
            ├── 김철수.m4a
            └── 홍길동.m4a
```

- 세션 폴더 `2026-09-08` 전체가 작업 하나입니다. 트랙을 각각 전사한 뒤
  시간순으로 정렬해 **하나의 전사본**으로 합칩니다.
- **화자 라벨은 파일 이름에서 확장자를 뺀 값**입니다 — 위 예시에서는
  `김철수`, `홍길동`. 그러니 파일 이름을 그대로 화자 이름으로 지으세요.
- 전사 결과: `~/Obsidian/second-brain/Transcripts/회의/2026-09-08/`
  (파일 이름이 아니라 **세션 폴더 이름**이 그대로 쓰입니다)
- 아카이브: `~/Transcribe/archive/회의/asr-multitrack/2026-09-08/`
  (파일 하나씩이 아니라 세션 폴더째 이동)

## 사용법

### 1. 파일 넣기

데몬이 떠 있는 상태에서 위 구조대로 파일을 복사하거나 옮겨 넣기만 하면
됩니다. 따로 실행할 명령은 없습니다. 다만 등록 시점이 모드에 따라 다릅니다:

- `asr` / `diarize`: 파일 크기가 **5초** 동안 더 늘어나지 않으면 복사가
  끝난 것으로 보고 작업으로 등록합니다.
- `asr-multitrack`: 세션 폴더 안에서 **60초** 동안 아무 변화가 없어야
  등록합니다. 트랙을 하나씩 천천히 넣는 도중에 세션이 불완전한 채로
  등록되는 것을 막기 위한 대기 시간입니다 — 모든 트랙을 다 넣은 뒤 1분
  정도 기다리세요.

작업은 한 번에 하나씩 순차 처리됩니다 (GPU 동시 실행 없음). 같은 내용의
파일을 다시 넣어도 중복 등록되지 않습니다 — 파일 이름이 아니라 내용
해시로 판별하기 때문에, 이름만 바꿔서 다시 넣어도 마찬가지입니다.

### 2. 성공했을 때

1. 전사 결과 4개 파일이
   `~/Obsidian/second-brain/Transcripts/<카테고리>/<라벨>/`에 발행됩니다:
   ```
   transcript.json   # 정본 — 세그먼트/단어 타임스탬프, 화자 라벨, 엔진·모델 메타데이터
   transcript.md     # [00:01:23] 화자: 텍스트 형태
   transcript.txt    # 타임스탬프 없이 본문만
   transcript.srt    # 자막 포맷
   ```
   `<라벨>`은 `asr`/`diarize`면 원본 파일 이름에서 확장자를 뺀 값,
   `asr-multitrack`이면 세션 폴더 이름 그대로입니다. 발행은 임시 폴더에
   전부 쓴 뒤 통째로 rename하는 방식이라, 절반만 쓰인 폴더가 vault에
   보이는 일은 없습니다.
2. 원본은 `~/Transcribe/archive/<카테고리>/<모드>/`로 **이동**합니다
   (인박스에서는 사라집니다). 모드 폴더를 생략하고 넣었던 파일도
   아카이브에서는 `asr/` 아래로 들어갑니다. 같은 이름이 이미 있으면 절대
   덮어쓰지 않고 내용 해시 앞 8자리를 붙여 저장합니다 —
   `2주차.m4a` → `2주차-1a2b3c4d.m4a` (그것마저 이미 있으면
   `2주차-1a2b3c4d-1.m4a`, `-2` … 순). 세션 폴더도 같은 방식으로
   `2026-09-08-1a2b3c4d`가 됩니다. 즉 아카이브에 이미 들어간 원본이
   조용히 유실되는 일은 없습니다.
3. macOS 알림이 뜹니다 — 제목 `전사 완료`, 본문 `<카테고리> · <원본 이름>`.
4. DB의 작업 상태가 `COMPLETED`가 됩니다.

### 3. 실패했을 때

- 작업 상태가 `FAILED`가 되고 에러 메시지가 DB에 기록됩니다.
- **원본 파일은 인박스에 그대로 남습니다.** 아카이브로 옮겨지지도, 삭제되지도
  않습니다. 전사 결과는 발행되지 않습니다.
- macOS 알림이 뜹니다 — 제목 `전사 실패`, 본문
  `<카테고리> · <원본 이름>: <에러 메시지>`.
- 실패한 작업은 데몬을 재시작해도 자동으로 재시도되지 **않습니다**. 파일이
  인박스에 남아 있어도 시작 시 스캔이 "이 내용은 이미 실패한 작업"으로 보고
  건너뜁니다 — 고장난 파일 하나 때문에 재시작할 때마다 GPU를 수십 분씩
  태우지 않기 위한 동작입니다. 재시도는 아래처럼 명시적으로 해야 합니다.

### 4. 상태 확인

작업 상태/이력은 로그 파일이 아니라 PostgreSQL에 저장됩니다. 상태 값은
`PENDING`(대기), `PROCESSING`(처리 중), `COMPLETED`(완료), `FAILED`(실패)
넷뿐입니다.

```sh
psql "$DATABASE_URL" -c "SELECT id, status, category, processing_mode, source_path, error_message, created_at FROM transcription_job ORDER BY created_at DESC LIMIT 10;"
```

실패한 작업만 보려면:

```sh
psql "$DATABASE_URL" -c "SELECT id, source_path, error_code, error_message FROM transcription_job WHERE status = 'FAILED';"
```

`psql`과 아래 `retry` 모두 **셸에** `DATABASE_URL`이 있어야 합니다 — plist에
넣은 값은 데몬 프로세스에만 적용되므로, 터미널에서는 따로
`export DATABASE_URL=...`를 해두세요.

### 5. 재시도

위 쿼리로 얻은 작업 id로 실행합니다 (프로젝트 디렉터리에서):

```sh
uv run transcribe-inbox retry <job-id>
```

이 명령은 작업 상태를 `FAILED` → `PENDING`으로 되돌려 놓기만 하며, 실제
처리는 데몬이 다음 폴링(약 5초 주기)에서 집어갑니다. 두 조건을 **모두**
만족해야 하고, 하나라도 어긋나면 아무것도 바꾸지 않은 채 에러 메시지를
출력하고 종료합니다:

1. 그 작업의 상태가 `FAILED`여야 합니다 —
   `PENDING`/`PROCESSING`/`COMPLETED`는 거부됩니다.
2. DB에 기록된 원본 경로에 파일(또는 세션 폴더)이 아직 존재해야 합니다 —
   실패한 원본을 인박스 밖으로 옮겼거나 지웠다면 재시도할 수 없습니다.

파일을 인박스에서 잠깐 뺐다가 다시 넣어도 같은 효과가 납니다 — 내용이
동일해도 실패 상태였던 작업은 다시 큐에 올라갑니다. 다만 원인이 파일 자체에
있다면(손상, 지원하지 않는 코덱 등) 몇 번을 재시도해도 결과는 같습니다.

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
