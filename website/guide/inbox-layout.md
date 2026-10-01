# Inbox layout

The only thing watched is `~/Transcribe/inbox/`. **How deep under this folder you place a file** directly determines its category and mode — there is no config file and no filename convention.

All you need to look at is the number of path components counted from `~/Transcribe/inbox/`:

| Path relative to the inbox | Category | Mode | Unit of work |
|---|---|---|---|
| `<파일>` | `미분류` (Uncategorized) | `asr` | that file |
| `<카테고리>/<파일>` | `<카테고리>` | `asr` | that file |
| `<카테고리>/asr/<파일>` | `<카테고리>` | `asr` | that file |
| `<카테고리>/diarize/<파일>` | `<카테고리>` | `diarize` | that file |
| `<카테고리>/asr-multitrack/<세션>/<파일>` | `<카테고리>` | `asr-multitrack` | the whole `<세션>` folder |

(Here `<파일>` is the file, `<카테고리>` the category folder, and `<세션>` the session folder.)

In words, the rules come down to four lines:

- The **category** is the name of the first folder directly under the inbox. The name is free-form (Korean names such as `강의` (lectures), `회의` (meetings) and `캡스톤` (capstone) can be used as-is), and you don't need to register a new category anywhere to use it — just create the folder.
- Dropping a file at the inbox root **without a category folder** also works normally; the category becomes `미분류` and the mode `asr`. The transcript goes under `~/Obsidian/second-brain/Transcripts/미분류/`, and the original goes to `~/Transcribe/archive/미분류/asr/`.
- The **mode folder** is the second folder and can be omitted. If omitted, it is `asr`. The name must match exactly one of `asr`, `asr-multitrack`, or `diarize` — names that differ in case or are variants, such as `ASR` or `multitrack`, are not recognized as a mode.
- Only `asr-multitrack` goes one level deeper. Under the mode folder you must put exactly one **session folder**, and put the per-speaker files directly inside it. A session folder is **a folder that groups the per-speaker files belonging to a single meeting**, and you can name it freely (`2026-09-08`, `주간회의` (weekly meeting), and so on). In this case the unit of work is the whole session folder, not the individual files.

Any path that doesn't fit one of the five forms above is treated as an **ambiguous path**: it is skipped and only logged — it is never processed by guessing. Cases that actually hit this:

```
~/Transcribe/inbox/강의/3장/2주차.m4a                              # 두 번째 폴더가 모드 이름이 아님
~/Transcribe/inbox/회의/asr-multitrack/회의록.m4a                  # 세션 폴더 없이 파일을 바로 넣음
~/Transcribe/inbox/회의/asr-multitrack/2026-09-08/원본/김철수.m4a  # 세션 폴더 아래에 또 폴더
```

(In order: the second folder is not a mode name; a file placed directly without a session folder; another folder under the session folder.)

The mode is determined solely by the folder structure — there is no way to set a permanent default such as "this category is always diarize"; every file's mode is decided on the spot by which folder path it was placed in. `~/Transcribe/archive/` (where originals are kept) and any other folder outside `~/Transcribe/inbox/` are never watched, even if they are siblings — you can freely store anything else there, including downloaded models (such as `~/Transcribe/model/`). Hidden files whose names start with `.` are ignored everywhere.
