# 문제 해결

## 데몬이 안 뜬다

plist를 `~/Library/LaunchAgents/`에 복사하고 `launchctl load`를 했는데도 프로세스가 떠 있지 않은 경우입니다. 먼저 실행 여부를 확인합니다:

```sh
launchctl list | grep transcribe-inbox
```

첫 번째 컬럼이 PID면 실행 중, `-`면 실행 중이 아닙니다 (두 번째 컬럼은 마지막 종료 코드).

- launchd 실행 실패(잘못된 바이너리 경로 등)는 `~/Library/Logs/transcribe-inbox.log`와 `~/Library/Logs/transcribe-inbox.error.log`가 **모두 비어 있습니다.** Python 프로세스 자체가 시작되지 못해 아무것도 쓸 수 없기 때문입니다.
- 두 로그가 모두 비어 있는데 데몬이 실행되지 않는다면, plist 안의 절대 경로(`uv`, `whisper-cli`, 모델 파일 등)가 틀렸을 가능성이 가장 큽니다. `which`/`ls`로 하나씩 다시 확인하세요.
- plist를 수정한 뒤에는 `launchctl unload` 후 다시 `launchctl load`를 해야 합니다. 파일만 덮어쓰는 것으로는 재적용되지 않습니다.

자세한 설치 절차와 각 값은 [설치 및 설정](/ko/getting-started/installation)과 [설정](/ko/reference/configuration)을 참고하세요.

## 세션이 FAILED가 된다

`asr-multitrack` 세션이 `FAILED`가 되는 흔한 원인은 세션 폴더에 화자별 오디오 외의 파일(`.txt`, `.dat` 등 메타데이터)이 섞여 있는 경우입니다. 세션 폴더 안의 숨김 파일이 아닌 모든 파일이 트랙으로 등록되어 오디오 디코딩을 시도하다 실패합니다. 세션 폴더 바로 아래에 화자별 오디오 파일만 두세요. 트랙의 시작 시각이 어긋난 경우의 주의점을 포함한 자세한 내용은 [지원하는 모드](/ko/guide/modes)를 참고하세요.

## 작업이 FAILED가 됐다

작업이 `FAILED`가 되면 에러 메시지가 DB에 기록되고, 원본 파일은 인박스에 그대로 남으며, 전사 결과는 발행되지 않습니다. 실패한 작업은 데몬을 재시작해도 자동으로 재시도되지 않으므로, 원인을 해결한 뒤 `retry` 명령으로 직접 다시 시도해야 합니다. 상태 확인 쿼리와 재시도 방법은 [사용법](/ko/guide/usage)을 참고하세요.
