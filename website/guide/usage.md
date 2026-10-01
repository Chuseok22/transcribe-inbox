# Usage

## How it works

```
~/Transcribe/inbox/<카테고리>/[모드]/... 에 파일을 넣으면
  → watchdog이 파일을 감지하고, 크기 증가가 멈출 때까지 대기(안정화 확인)
  → PostgreSQL에 작업(job)으로 등록 (대기·처리 중·완료 상태인 같은 내용은 중복 등록되지 않음)
  → 워커가 작업을 하나씩 순차적으로 가져감 (GPU 작업 동시 실행 없음)
  → ffmpeg가 오디오를 16kHz mono WAV로 추출/리샘플링
    (비디오 컨테이너도 처리함. "사전 준비물" 페이지의 "지원하는 입력 포맷" 참고;
    무음 구간을 잘라내지 않으므로 전사 결과의 타임스탬프는 항상 원본과 일치함)
  → 모드에 따라 엔진으로 라우팅:
      asr / asr-multitrack → whisper.cpp (단일 화자, 또는 사전 분리된 트랙)
      diarize               → whispermlx (다중 화자 회의, 화자 라벨 추가)
  → transcript.json(정본) + .md/.txt/.srt 파일을 Obsidian vault에 저장
  → 원본 파일은 아카이브로 이동, macOS 알림 발송
```

The diagram is in Korean. `<카테고리>` is the category (the first folder under the
inbox) and `[모드]` is the optional mode folder. The steps:

1. You put a file into the inbox.
2. watchdog detects it and waits until its size stops growing.
3. The file is registered as a job in PostgreSQL. A file with the same content is
   not queued again while a job for it is `PENDING`, `PROCESSING` or `COMPLETED`.
4. The worker takes jobs one at a time. GPU work does not run in parallel.
5. ffmpeg extracts and resamples the audio to 16kHz mono WAV. This works for
   video containers too (see "Supported input formats" in
   [Prerequisites](/getting-started/prerequisites)). Silence is not trimmed, so
   transcript timestamps always match the original.
6. The mode picks the engine: whisper.cpp for `asr` and `asr-multitrack` (one
   speaker, or tracks already split per speaker), whispermlx for `diarize`
   (meetings with several speakers, adds speaker labels).
7. `transcript.json` (the canonical file) and the `.md`, `.txt` and `.srt` files
   are saved to the Obsidian vault.
8. The original moves to the archive and a macOS notification is sent.

## When the daemon restarts

When the daemon restarts after a crash, a reboot or similar, it brings job states
back in line at startup. Jobs that stopped mid-processing go back into the queue.
If the original is gone, the job is marked failed. Jobs whose transcription
finished but whose original was not moved to the archive are archived at this
point.

## Adding files

While the daemon runs, copy or move files into the inbox following the
[Inbox layout](/guide/inbox-layout). There is no command to run. When a file
becomes a job depends on the mode.

- `asr` / `diarize`: when the file size has not grown for 5 seconds, the copy is
  treated as finished and the job is registered.
- `asr-multitrack`: the session folder must have no changes for 60 seconds. The
  wait keeps an incomplete session from being registered while you add tracks one
  by one. After adding all tracks, wait about a minute.

Jobs run one at a time, in order. GPU work does not run in parallel. Adding a
file with the same content again does not register it twice if a job for that
content is `PENDING`, `PROCESSING` or `COMPLETED`. Files are matched by a hash of
their content, not by name, so a renamed copy is also not registered again. If
the earlier job is `FAILED`, the file is registered again when you drop it into
the inbox again.

## When a job fails

- The job status changes to `FAILED` and the error message is recorded in the DB.
- The original file stays in the inbox. It is not archived or deleted. A
  transcript is usually not saved, but it can already exist in the output folder
  if saving finished and only recording completion failed.
- A macOS notification appears. The title is `전사 실패` ("Transcription
  failed") and the body is `<카테고리> · <원본 이름>: <에러 메시지>`
  (`<category> · <original name>: <error message>`).
- A failed job is **not retried automatically**, even after a daemon restart. If
  the file is still in the inbox, the startup scan sees it as a job that already
  failed and skips it. This keeps one broken file from using tens of minutes of
  GPU time on every restart. To retry, use one of the methods below.

## Checking status

Job status and history are stored in PostgreSQL, not in log files. There are four
status values: `PENDING` (waiting), `PROCESSING` (in progress), `COMPLETED`
(done) and `FAILED` (failed).

```sh
psql "$DATABASE_URL" -c "SELECT id, status, category, processing_mode, source_path, error_message, created_at FROM transcription_job ORDER BY created_at DESC LIMIT 10;"
```

To list only failed jobs:

```sh
psql "$DATABASE_URL" -c "SELECT id, source_path, error_code, error_message FROM transcription_job WHERE status = 'FAILED';"
```

`psql` and the `retry` command below need `DATABASE_URL` in your shell. The value
in the plist applies only to the daemon process, so run `export DATABASE_URL=...`
in the terminal.

## Retrying

Run this from the project directory with the job id from the query above.

```sh
uv run transcribe-inbox retry <job-id>
```

The command only changes the job status from `FAILED` back to `PENDING`. The
daemon picks the job up on its next poll (about every 5 seconds). Both
conditions below must hold. If either fails, the command changes nothing, prints
an error message and exits.

1. The job status is `FAILED`. Jobs in `PENDING`, `PROCESSING` or `COMPLETED`
   are rejected.
2. The file (or session folder) still exists at the original path recorded in
   the DB. If you moved the failed original out of the inbox or deleted it, you
   cannot retry.

Taking the file out of the inbox and putting it back has the same effect. A job
that failed is queued again even if the content is the same. If the file itself
is the cause (corruption, an unsupported codec and so on), retrying gives the same
result every time.
