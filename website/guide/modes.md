# Modes

There are three modes.

| Mode | When to use it | Engine | Speaker labels |
|---|---|---|---|
| `asr` (default) | Recordings with one speaker (lectures, solo voice memos) | whisper.cpp | none |
| `asr-multitrack` | Recordings already split into one file per speaker (a meeting where each participant recorded on their own device) | whisper.cpp (once per track) | track file name (without extension) |
| `diarize` | Recordings with several speakers mixed in one file (a meeting recorded with one microphone) | whispermlx | anonymous labels from the diarization model |

`diarize` separates speakers and `asr` does not. Transcription quality does not
differ between them. If you do not need speakers separated, there is no reason to
use `diarize`. It runs extra alignment and diarization steps, so it takes much
longer.

If you already have one file per speaker, use `asr-multitrack` rather than
`diarize`. Diarization is an inference and can get speakers wrong. In
`asr-multitrack` each file belongs to a known speaker, so the labels cannot be
wrong.

## `asr`: single speaker (default)

Leave out the mode folder. In these examples `강의` is the category (lectures).

```
~/Transcribe/inbox/
└── 강의/
    └── 2주차.m4a
```

- Transcript: `~/Obsidian/second-brain/Transcripts/강의/2주차/`
- Archive: `~/Transcribe/archive/강의/asr/2주차.m4a`

Naming the mode folder, as in `~/Transcribe/inbox/강의/asr/2주차.m4a`, gives the
same result.

## `diarize`: a meeting with several speakers in one file

Here `회의` is the category (meetings).

```
~/Transcribe/inbox/
└── 회의/
    └── diarize/
        └── 2026-09-08.m4a
```

- Transcript: `~/Obsidian/second-brain/Transcripts/회의/2026-09-08/`
- Archive: `~/Transcribe/archive/회의/diarize/2026-09-08.m4a`
- Speaker labels are anonymous labels from the diarization model, not real names.
  You match them to people yourself by reading the transcript.
- Only this mode needs `HUGGINGFACE_TOKEN` and acceptance of the model terms (see
  [Prerequisites](/getting-started/prerequisites)).

## `asr-multitrack`: a meeting with one file per speaker

Create one session folder under the mode folder and put the per-speaker files in
it.

```
~/Transcribe/inbox/
└── 회의/
    └── asr-multitrack/
        └── 2026-09-08/
            ├── 김철수.m4a
            └── 홍길동.m4a
```

- The session folder `2026-09-08` is one job. Each track is transcribed, then the
  results are sorted by time and merged into one transcript.
- The speaker label is the file name without its extension: `김철수` and `홍길동`
  in the example above. Name each file after its speaker.
- Transcript: `~/Obsidian/second-brain/Transcripts/회의/2026-09-08/`
  (uses the session folder name, not a file name)
- Archive: `~/Transcribe/archive/회의/asr-multitrack/2026-09-08/`
  (the whole session folder moves, not one file at a time)

**Warning: put only per-speaker audio files in the session folder.**

- Every file in the session folder except hidden files is registered as a track.
  If a metadata file such as `.txt` or `.dat` is there, decoding it as audio
  fails and the whole session becomes `FAILED`. Failed jobs are not retried
  automatically (see "When a job fails" in [Usage](/guide/usage)).
- All tracks are assumed to start at the same time. Per-track start offsets are
  not supported. Every track is treated as starting at 0 seconds and merged by
  time. If the tracks started recording at different times, the order of lines in
  the merged transcript can be wrong. Check first that the per-speaker files
  started recording at the same moment.
- Put files directly under the session folder. Do not create subfolders inside it
  (see "ambiguous path" in [Inbox layout](/guide/inbox-layout)).

### Example: a Discord meeting recorded with Craig

A multitrack download from Craig contains metadata files next to the per-speaker
audio.

```
craig-xxxxxxxx/
├── 1-alice.aac             # 화자별 트랙 (앞에 번호가 붙음)
├── 2-bob.aac
├── 3-carol.aac
├── info.txt               # 메타데이터 — 넣으면 안 됨
└── raw.dat                # 원본 데이터 — 넣으면 안 됨
```

The comments say: per-speaker track (with a number prefix); metadata, do not
include; raw data, do not include.

Do not put the whole folder in. Copy only the audio files into a session folder.
The speaker label comes from the file name, so it is best to remove the number
prefix
(`1-alice.aac` → `alice.aac`).

```
~/Transcribe/inbox/
└── 회의/
    └── asr-multitrack/
        └── 2026-09-26/          ← 세션 폴더
            ├── alice.aac
            ├── bob.aac
            └── carol.aac
```

`← 세션 폴더` marks the session folder.

When transcription succeeds, the originals in the inbox move to the archive. Copy
the downloaded folder's files in rather than moving them.
