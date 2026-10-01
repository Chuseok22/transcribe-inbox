# Modes

There are exactly three modes.

| Mode | When to use it | Engine | Speaker labels |
|---|---|---|---|
| `asr` (default) | Recordings with a single speaker — lectures, solo voice memos | whisper.cpp | none |
| `asr-multitrack` | Recordings that are **already split per speaker** — meetings where each participant recorded on their own device | whisper.cpp (once per track) | the track file name (without extension) |
| `diarize` | Recordings where several speakers are **mixed into one file** — a meeting recorded with a single microphone | whispermlx | anonymous labels assigned by the diarization model |

The difference between `asr` and `diarize` is not transcription quality but whether speakers are told apart. If you don't need to separate speakers, there is no reason to use `diarize` — it takes considerably longer because the alignment and diarization steps run additionally.

If you already have per-speaker files, `asr-multitrack` is better than `diarize`. Diarization is inference and can be wrong, but with `asr-multitrack` it is already settled which file belongs to whom, so the speaker labels have no room to be wrong.

## `asr` — single speaker (default)

Just omit the mode folder (here `강의` is the category, e.g. `lectures`):

```
~/Transcribe/inbox/
└── 강의/
    └── 2주차.m4a
```

- Transcript: `~/Obsidian/second-brain/Transcripts/강의/2주차/`
- Archive: `~/Transcribe/archive/강의/asr/2주차.m4a`

Specifying the mode explicitly, as in `~/Transcribe/inbox/강의/asr/2주차.m4a`, gives exactly the same result.

## `diarize` — a meeting with several speakers mixed into one file

```
~/Transcribe/inbox/
└── 회의/
    └── diarize/
        └── 2026-09-08.m4a
```

- Transcript: `~/Obsidian/second-brain/Transcripts/회의/2026-09-08/`
- Archive: `~/Transcribe/archive/회의/diarize/2026-09-08.m4a`
- The speaker labels are anonymous labels that the diarization model assigns automatically — they are not real people's names, and you have to map who is who yourself by reading the transcript.
- Only this mode needs `HUGGINGFACE_TOKEN` and acceptance of the model's terms (see [Prerequisites](/getting-started/prerequisites)).

## `asr-multitrack` — a meeting split into per-speaker files

Create one session folder under the mode folder and put the per-speaker files inside it:

```
~/Transcribe/inbox/
└── 회의/
    └── asr-multitrack/
        └── 2026-09-08/
            ├── 김철수.m4a
            └── 홍길동.m4a
```

- The whole session folder `2026-09-08` is one job. Each track is transcribed separately, then they are sorted chronologically and merged into **one transcript**.
- **The speaker label is the file name minus its extension** — `김철수` and `홍길동` in the example above. So name the files after the speakers directly.
- Transcript: `~/Obsidian/second-brain/Transcripts/회의/2026-09-08/` (the **session folder name** is used as-is, not a file name)
- Archive: `~/Transcribe/archive/회의/asr-multitrack/2026-09-08/` (moved as a whole session folder, not file by file)

**Caution — put only the per-speaker audio files in the session folder.**

- **Every (non-hidden) file in the session folder is registered as a track.** If a metadata file such as `.txt` or `.dat` is mixed in, that file is also fed to audio decoding and fails, and **the entire session becomes `FAILED`**. A failed job is not retried automatically (see "When a job fails" in [Usage](/guide/usage)).
- **All tracks are assumed to start at the same time.** Per-track start-time correction (offsets) is not supported; everything is set to 0 seconds and merged chronologically. If the recording start times of the tracks are misaligned, the order of utterances in the merged transcript can be wrong, so first check that the per-speaker files are recordings that start from the same moment.
- Place files **directly under** the session folder only. You must not create subfolders inside it (see "ambiguous path" in [Inbox layout](/guide/inbox-layout)).

### Example: a Discord meeting recorded with Craig

The folder you download from Craig as multitrack contains metadata files alongside the per-speaker audio:

```
craig-xxxxxxxx/
├── 1-alice.aac             # 화자별 트랙 (앞에 번호가 붙음)
├── 2-bob.aac
├── 3-carol.aac
├── info.txt               # 메타데이터 — 넣으면 안 됨
└── raw.dat                # 원본 데이터 — 넣으면 안 됨
```

(Comments in the listing: per-speaker tracks, with a number prefix; metadata — must not be included; raw data — must not be included.)

Don't put this folder in as a whole — **pick out only the audio files and copy them into a session folder**. Since the speaker label comes from the file name, it is recommended to strip the number prefix (`1-alice.aac` → `alice.aac`):

```
~/Transcribe/inbox/
└── 회의/
    └── asr-multitrack/
        └── 2026-09-26/          ← 세션 폴더
            ├── alice.aac
            ├── bob.aac
            └── carol.aac
```

(`← 세션 폴더` means "session folder".)

When the transcription succeeds, the original in the inbox is **moved** to the archive, so **copy** the files in rather than moving your original download folder.
