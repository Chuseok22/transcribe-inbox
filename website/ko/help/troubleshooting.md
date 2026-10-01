# 문제 해결

## 데몬이 실행되지 않을 때

plist를 `~/Library/LaunchAgents/`에 복사하고 `launchctl load`를 실행했는데 프로세스가 없는 경우입니다. 먼저 실행 여부를 확인합니다.

```sh
launchctl list | grep transcribe-inbox
```

첫 번째 컬럼이 PID면 실행 중이고, `-`면 실행 중이 아닙니다. 두 번째 컬럼은 마지막 종료 코드입니다.

- 잘못된 바이너리 경로처럼 launchd 단계에서 실행에 실패하면 `~/Library/Logs/transcribe-inbox.log`와 `~/Library/Logs/transcribe-inbox.error.log`가 모두 비어 있습니다. Python 프로세스가 시작되지 않아 로그를 쓰지 못하기 때문입니다.
- 두 로그가 모두 비어 있는데 데몬이 실행되지 않는다면, plist에 적은 절대 경로(`uv`, `whisper-cli`, 모델 파일 등) 중 하나가 틀렸을 가능성이 가장 큽니다. `which`나 `ls`로 하나씩 확인하세요.
- plist를 수정한 뒤에는 `launchctl unload` 후 `launchctl load`를 다시 실행해야 합니다. 파일만 덮어써서는 반영되지 않습니다.

설치 절차와 각 값은 [설치 및 설정](/ko/getting-started/installation)과 [설정](/ko/reference/configuration)을 참고하세요.

## 세션이 FAILED가 될 때

`asr-multitrack` 세션이 `FAILED`가 되는 흔한 원인은 세션 폴더에 화자별 오디오가 아닌 파일(`.txt`, `.dat` 같은 메타데이터)이 섞인 경우입니다. 세션 폴더 안의 파일은 숨김 파일을 빼고 모두 트랙으로 등록되므로, 이런 파일도 오디오로 디코딩하려다 실패합니다. 세션 폴더 바로 아래에는 화자별 오디오 파일만 두세요. 트랙 시작 시각이 어긋난 경우의 주의점을 포함한 자세한 내용은 [지원하는 모드](/ko/guide/modes)에 있습니다.

## 작업이 FAILED가 됐을 때

작업이 `FAILED`가 되면 에러 메시지가 DB에 기록됩니다. 원본 파일은 인박스에 그대로 남고, 전사 결과는 저장되지 않습니다. 실패한 작업은 데몬을 재시작해도 자동으로 재시도하지 않으므로, 원인을 해결한 뒤 `retry` 명령으로 직접 재시도하세요. 상태 확인 쿼리와 재시도 방법은 [사용법](/ko/guide/usage)에 있습니다.
