# 설정

launchd 데몬은 plist의 `EnvironmentVariables`에서 설정을 읽습니다. 설치할 때 `launchd/com.chuseok22.transcribe-inbox.plist`를 복사해 아래 값을 채웁니다.

## plist 키

| 키 | 의미 | 참고 |
|---|---|---|
| `ProgramArguments[0]` | `uv`의 절대 경로 | `which uv`로 확인합니다. 설치 방식(Homebrew, 공식 설치 스크립트 등)에 따라 경로가 다르므로 `/opt/homebrew/bin/uv`라고 가정하지 마세요 |
| `DATABASE_URL` | PostgreSQL 접속 문자열 | 예: `postgresql://user:password@localhost:5432/transcribe_inbox` |
| `WHISPER_CLI_BINARY` | `whisper-cli` 경로 | `which whisper-cli`로 확인 |
| `WHISPER_VAD_MODEL_PATH` | `ggml-silero-v6.2.0.bin` 경로 | 다운로드한 위치 |
| `WHISPER_ASR_MODEL_PATH` | `ggml-large-v3.bin` 경로 | 다운로드한 위치 |
| `WHISPER_MLX_MODEL_PATH` | HuggingFace 저장소 ID | 파일 경로가 아닙니다. 기본값으로는 `mlx-community/whisper-large-v3-mlx`가 무난합니다 |
| `HUGGINGFACE_TOKEN` | 발급받은 Read 권한 토큰 | `diarize` 모드에서만 필요합니다. 다만 해당 엔진으로 라우팅될 때 코드가 항상 이 값을 읽으므로, `diarize`를 쓰지 않더라도 더미 값을 넣어 두세요 |
| `PATH` | `uv`가 있는 디렉터리를 포함 | launchd는 셸의 `PATH`를 상속하지 않습니다. 데몬이 실행하는 모든 외부 바이너리는 여기에 적은 디렉터리에서 찾을 수 있어야 하며, 기본 `PATH`에 있으리라 가정하면 안 됩니다 |

## 경로 설정 (선택)

입력, 보관, 출력 폴더는 환경변수로 바꿀 수 있습니다. 이 값은 셸이 아니라 데몬 프로세스가 읽습니다. 그래서 plist의 `EnvironmentVariables`에 넣어야 하며, 터미널에서 `export`해도 효과가 없습니다.

| 용도 | 환경변수 | 기본값 |
|---|---|---|
| 입력(감시) 폴더 | `TRANSCRIBE_INBOX_ROOT` | `~/Transcribe/inbox` |
| 원본 보관 폴더 | `TRANSCRIBE_ARCHIVE_ROOT` | `~/Transcribe/archive` |
| 전사 결과 출력 폴더 | `OBSIDIAN_TRANSCRIPTS_ROOT` | `~/Obsidian/second-brain/Transcripts` |

- 출력 폴더가 Obsidian vault일 필요는 없습니다. 환경변수 이름은 `OBSIDIAN_*`이지만 일반 폴더도 됩니다. 결과는 `transcript.json`, `.md`, `.txt`, `.srt` 파일이므로 Obsidian 없이 쓸 수 있습니다.
- 임시 작업 폴더(`.staging`)는 출력 폴더 아래에 만들어집니다. 그래서 결과를 저장할 때 일어나는 폴더 이름 변경이 같은 볼륨 안에서 처리됩니다.
- 원본 보관 폴더는 입력 폴더와 다른 볼륨에 있어도 됩니다. 볼륨이 다르면 이동이 복사 후 삭제로 처리되어 원자적이지 않습니다.
- 카테고리 없이 인박스 루트에 둔 파일의 카테고리 이름 `미분류`는 코드에 고정되어 있어 바꿀 수 없습니다.
