# Usage

## How it works

```
~/Transcribe/inbox/<카테고리>/[모드]/... 에 파일을 넣으면
  → watchdog이 파일을 감지하고, 크기 증가가 멈출 때까지 대기(안정화 확인)
  → PostgreSQL에 작업(job)으로 등록 (idempotent — 같은 내용의 파일은 절대 중복 큐잉되지 않음)
  → 워커가 작업을 하나씩 순차적으로 가져감 (GPU 작업 동시 실행 없음)
  → ffmpeg가 오디오를 16kHz mono WAV로 추출/리샘플링
    (오디오뿐 아니라 비디오 컨테이너에서도 동작 — "사전 준비물" 페이지의 "지원하는 입력 포맷" 참고;
    무음 구간을 절대 잘라내지 않으므로, 전사 결과의 타임스탬프는 항상 원본과 일치함)
  → 모드에 따라 엔진으로 라우팅:
      asr / asr-multitrack → whisper.cpp (단일 화자, 또는 사전 분리된 트랙)
      diarize               → whispermlx (다중 화자 회의, 화자 라벨 추가)
  → transcript.json(정본) + .md/.txt/.srt 파일을 Obsidian vault에 발행
  → 원본 파일은 아카이브로 이동, macOS 알림 발송
```

In the diagram: `<카테고리>` is the category (the first folder under the inbox) and `[모드]` the optional mode folder; the steps are: detect and wait for the file to stabilize, register the job in PostgreSQL, process sequentially, extract audio with ffmpeg, route to an engine by mode, publish the transcript files, then archive the original and notify.

## When the daemon restarts

When the daemon restarts (a crash, a reboot, and so on), it reconciles its own state at startup: jobs that were stuck mid-processing are re-queued (or marked as failed if the original has disappeared), and jobs whose transcription finished but that could not be moved to the archive are archived at this point.

## Adding files

With the daemon running, just copy or move files in following the [Inbox layout](/guide/inbox-layout). There is no command to run. However, the registration timing depends on the mode:

- `asr` / `diarize`: once the file size stops growing for **5 seconds**, the copy is considered finished and the job is registered.
- `asr-multitrack`: nothing must change inside the session folder for **60 seconds** before it is registered. This wait exists to prevent a session from being registered incomplete while you are slowly adding tracks one at a time — after putting in all the tracks, wait about a minute.

Jobs are processed one at a time, sequentially (no concurrent GPU runs). Putting in a file with the same content again does not register it twice — since this is decided by the content hash rather than the file name, the same holds even if you only rename it and put it in again.


## When a job fails

- The job status becomes `FAILED` and the error message is recorded in the DB.
- **The original file stays in the inbox as it is.** It is neither moved to the archive nor deleted. No transcript is published.
- A macOS notification appears — title `전사 실패`, body `<카테고리> · <원본 이름>: <에러 메시지>`. (The title means "Transcription failed"; the body is `<category> · <original name>: <error message>`.)
- A failed job is **not** retried automatically even when you restart the daemon. Even if the file remains in the inbox, the startup scan sees it as "this content already failed as a job" and skips it — this behavior keeps a single broken file from burning tens of minutes of GPU on every restart. Retrying must be done explicitly, as described below.

## Checking status

Job status/history is stored in PostgreSQL, not in log files. There are only four status values: `PENDING` (waiting), `PROCESSING` (in progress), `COMPLETED` (done), and `FAILED` (failed).

```sh
psql "$DATABASE_URL" -c "SELECT id, status, category, processing_mode, source_path, error_message, created_at FROM transcription_job ORDER BY created_at DESC LIMIT 10;"
```

To see only failed jobs:

```sh
psql "$DATABASE_URL" -c "SELECT id, source_path, error_code, error_message FROM transcription_job WHERE status = 'FAILED';"
```

Both `psql` and `retry` below need `DATABASE_URL` **in your shell** — the value you put in the plist applies only to the daemon process, so in the terminal run a separate `export DATABASE_URL=...`.

## Retrying

Run it with the job id obtained from the query above (from the project directory):

```sh
uv run transcribe-inbox retry <job-id>
```

This command only flips the job status from `FAILED` back to `PENDING`; the actual processing is picked up by the daemon on its next poll (about every 5 seconds). **Both** conditions must be met, and if either one fails, it changes nothing, prints an error message, and exits:

1. The job's status must be `FAILED` — `PENDING`/`PROCESSING`/`COMPLETED` are rejected.
2. The file (or session folder) must still exist at the original path recorded in the DB — if you moved the failed original out of the inbox or deleted it, you cannot retry.

Taking the file out of the inbox briefly and putting it back has the same effect — even if the content is identical, a job that was in the failed state is queued again. However, if the cause lies in the file itself (corruption, an unsupported codec, and so on), the result is the same no matter how many times you retry.
