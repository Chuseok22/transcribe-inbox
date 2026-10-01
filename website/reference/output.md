# Output & archive

## When it succeeds

1. Four transcript files are published to `~/Obsidian/second-brain/Transcripts/<카테고리>/<라벨>/` (`<카테고리>` is the category, `<라벨>` the label):
   ```
   transcript.json   # 정본 — 세그먼트/단어 타임스탬프, 화자 라벨, 엔진·모델 메타데이터
   transcript.md     # [00:01:23] 화자: 텍스트 형태
   transcript.txt    # 타임스탬프 없이 본문만
   transcript.srt    # 자막 포맷
   ```
   (Comments, in order: canonical — segment/word timestamps, speaker labels, engine/model metadata; in the form `[00:01:23] speaker: text`; body text only, without timestamps; subtitle format.)

   `<라벨>` is the original file name minus its extension for `asr`/`diarize`, and the session folder name as-is for `asr-multitrack`. Publishing writes everything to a temporary folder and then renames it as a whole, so a half-written folder is never visible in the vault.
2. The original is **moved** to `~/Transcribe/archive/<카테고리>/<모드>/` (`<모드>` is the mode; it disappears from the inbox). A file that was put in with the mode folder omitted also goes under `asr/` in the archive. If the same name already exists, it is never overwritten; the first 8 characters of the content hash are appended instead — `2주차.m4a` → `2주차-1a2b3c4d.m4a` (and if even that already exists, `2주차-1a2b3c4d-1.m4a`, then `-2`, and so on). A session folder becomes `2026-09-08-1a2b3c4d` in the same way. In other words, an original that is already in the archive is never silently lost.
3. A macOS notification appears — title `전사 완료` ("Transcription complete"), body `<카테고리> · <원본 이름>` (`<category> · <original name>`).
4. The job status in the DB becomes `COMPLETED`.
