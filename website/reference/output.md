# Output & archive

## When a job succeeds

1. Four transcript files are saved to
   `~/Obsidian/second-brain/Transcripts/<카테고리>/<라벨>/`, where `<카테고리>` is
   the category and `<라벨>` the label.
   ```
   transcript.json   # 정본 — 세그먼트/단어 타임스탬프, 화자 라벨, 엔진·모델 메타데이터
   transcript.md     # [00:01:23] 화자: 텍스트 형태
   transcript.txt    # 타임스탬프 없이 본문만
   transcript.srt    # 자막 포맷
   ```
   The comments, in order: the canonical file, with segment and word timestamps,
   speaker labels and engine and model metadata; lines in the form
   `[00:01:23] speaker: text`; body text only, without timestamps; subtitle format.

   For `asr` and `diarize`, `<라벨>` is the original file name without its
   extension. For `asr-multitrack`, it is the session folder name. All results
   are written to a temporary folder first, and then the folder is renamed. A
   half-written folder therefore does not show up in the vault.
2. The original moves to `~/Transcribe/archive/<카테고리>/<모드>/` (`<모드>` is
   the mode) and is removed from the inbox. A file added without a mode folder
   also goes under `asr/` in the archive. If the same name already exists, the
   file is not overwritten. The first 8 characters of the content hash are added
   to the name instead. For example, `2주차.m4a` becomes `2주차-1a2b3c4d.m4a`. If
   that name exists too, it becomes `2주차-1a2b3c4d-1.m4a`, then `-2` and so on.
   A session folder becomes `2026-09-08-1a2b3c4d` in the same way. An original
   already in the archive is not overwritten or lost.
3. A macOS notification appears. The title is `전사 완료` ("Transcription
   complete") and the body is `<카테고리> · <원본 이름>`
   (`<category> · <original name>`).
4. The job status in the DB changes to `COMPLETED`.

In practice, `COMPLETED` is recorded right after the transcript folder is saved, before the notification and the archive. If either of those fails, the job stays `COMPLETED` and the transcript is already saved. The original then stays in the inbox and is archived at the next daemon start.
