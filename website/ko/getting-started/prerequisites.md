# 사전 준비물

## 지원하는 입력 포맷

`ffmpeg`가 오디오를 디코딩할 수 있는 포맷이면 오디오와 비디오를 모두
지원합니다. 파이프라인은 파일 확장자를 검사하지 않고
`ffmpeg -i <파일> -ar 16000 -ac 1 <wav>`를 실행합니다. 이 명령은 컨테이너
종류와 관계없이 `ffmpeg`가 찾은 오디오 스트림을 추출하고 리샘플링합니다.

직접 확인한 포맷은 `.m4a`(갤럭시 음성 녹음기 파일)와 오디오 트랙이 있는
`.mp4`/`.mov` 계열 비디오 컨테이너입니다. 비디오에서는 `ffmpeg`가 오디오
트랙만 추출하고, 이후 단계는 비디오 스트림을 다루지 않습니다.

손상되었거나 지원하지 않는 코덱이라 `ffmpeg`가 디먹싱하지 못하는 파일은 해당
작업만 실패 처리되고, DB에 에러가 기록됩니다. 데몬은 계속 실행되며 다른
작업에도 영향이 없습니다.

## 필요한 것들

- 로컬에서 실행 중인 PostgreSQL. 작업 큐와 상태 저장소로 씁니다. 전사 내용은
  여기에 저장하지 않고 작업 상태와 메타데이터만 저장합니다.
- `ffmpeg`:
  ```sh
  brew install ffmpeg
  ```
- `whisper-cli` (whisper.cpp의 CLI 바이너리). PyPI 패키지가 아닙니다.
  ```sh
  brew install whisper-cpp
  which whisper-cli   # 설치 경로 확인, 아래에서 사용됨
  ```
  이 프로젝트는 whisper.cpp의 특정 git 태그나 커밋을 아직 고정하지 않아서
  `brew`의 `stable` 버전을 그대로 받습니다. 알려진 한계입니다.
- whisper.cpp 모델 파일 2개. 파일을 하나씩 내려받으세요. HuggingFace 저장소를
  통째로 받으면 안 됩니다. 이 저장소들에는 모든 크기와 양자화 버전의 모델이
  들어 있어 합치면 수십 GB입니다.
  - ASR 모델: [`ggml-large-v3.bin`](https://huggingface.co/ggerganov/whisper.cpp/tree/main).
    정확도를 위해 양자화하지 않은 `large-v3`로 고정되어 있으며, 크기는 수 GB입니다.
  - VAD 모델: [`ggml-silero-v6.2.0.bin`](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin).
    ASR 모델과 다른 HuggingFace 저장소에 있습니다. 크기는 1MB 미만입니다.
- `whispermlx` (`diarize` 모드에서 사용). [설치 및 설정](/ko/getting-started/installation)의
  `uv sync`로 함께 설치되므로 별도 설치 단계가 없습니다. ASR, 정렬(alignment),
  화자분리 모델은 직접 내려받는 로컬 파일이 아닙니다. `whispermlx`가 처음 쓸 때
  HuggingFace에서 받아 `~/.cache/huggingface/` 아래에 캐시하고,
  `mlx-community/whisper-large-v3-mlx` 같은 모델 이름으로 구분합니다.
  [설정](/ko/reference/configuration)의 `WHISPER_MLX_MODEL_PATH`에 넣는 값이 이
  문자열입니다. 이름에 "PATH"가 들어 있지만 값은 파일 경로가 아니라
  HuggingFace 저장소 ID입니다.
- `diarize` 모드(다중 화자 회의)를 쓰려면 HuggingFace 액세스 토큰이 필요합니다.
  화자분리 모델이 승인이 필요한(gated) 모델이기 때문입니다.
  1. huggingface.co → Settings → Access Tokens에서 Read 권한 토큰을 발급하세요.
     이 프로젝트는 모델을 내려받아 쓰기만 하고 업로드하지 않으므로 Read
     권한이면 충분합니다.
  2. https://huggingface.co/pyannote/speaker-diarization-community-1 에서 모델
     이용 약관에 동의하세요. 동의하지 않으면 토큰이 유효해도 화자분리가
     실행 중에 실패합니다.
- macOS `osascript`. 알림을 보낼 때 쓰며, 모든 Mac에 기본으로 들어 있습니다.
