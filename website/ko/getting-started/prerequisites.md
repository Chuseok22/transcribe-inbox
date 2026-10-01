# 사전 준비물

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

## 필요한 것들

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
- `whispermlx` (`diarize` 모드에서 사용) — [설치 및 설정](/ko/getting-started/installation)의 `uv sync`로 자동 설치되며,
  별도 설치 단계가 필요 없습니다. 실제 ASR/정렬(alignment)/화자분리 모델은
  직접 다운로드하는 로컬 파일이 **아닙니다** — `whispermlx`가 처음 사용할 때
  HuggingFace에서 자동으로 받아서 `~/.cache/huggingface/` 아래에 캐싱하며,
  `mlx-community/whisper-large-v3-mlx` 같은 모델 이름으로 식별됩니다 ([설정](/ko/reference/configuration)의
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
