# Inbox layout

The daemon watches one folder, `~/Transcribe/inbox/`. The depth at which you put a
file under it sets the category and the mode. There is no separate config file
and no file naming rule.

Count the path components from `~/Transcribe/inbox/`.

| Path relative to the inbox | Category | Mode | Unit of work |
|---|---|---|---|
| `<파일>` | `미분류` (Uncategorized) | `asr` | that file |
| `<카테고리>/<파일>` | `<카테고리>` | `asr` | that file |
| `<카테고리>/asr/<파일>` | `<카테고리>` | `asr` | that file |
| `<카테고리>/diarize/<파일>` | `<카테고리>` | `diarize` | that file |
| `<카테고리>/asr-multitrack/<세션>/<파일>` | `<카테고리>` | `asr-multitrack` | the whole `<세션>` folder |

In the table, `<파일>` is the file, `<카테고리>` the category folder and `<세션>`
the session folder.

The rules in detail:

- The category is the name of the first folder directly under the inbox. You can
  name it anything, including Korean names such as `강의`, `회의` or `캡스톤`
  (lectures, meetings, capstone). To add a category, create the folder. There is
  nothing to register.
- A file placed at the inbox root, with no category folder, is processed too. Its
  category is `미분류` and its mode is `asr`. The transcript is saved under
  `~/Obsidian/second-brain/Transcripts/미분류/`, and the original moves to
  `~/Transcribe/archive/미분류/asr/`.
- The mode folder is the second folder and is optional. Without it, the mode is
  `asr`. The folder name must match `asr`, `asr-multitrack` or `diarize`
  character for character. A name with different case such as `ASR`, or a short
  form such as `multitrack`, is not treated as a mode.
- `asr-multitrack` goes one level deeper. Under the mode folder, create one
  session folder and put the per-speaker files directly in it. A **session
  folder** groups the per-speaker files of one meeting. Name it as you like, for
  example `2026-09-08` or `주간회의` (weekly meeting). In this mode the whole
  session folder is one job.

A path that does not match one of the five forms above is treated as an ambiguous
path. It is skipped and logged. The daemon does not guess what you meant. These
paths are ambiguous:

```
~/Transcribe/inbox/강의/3장/2주차.m4a                              # 두 번째 폴더가 모드 이름이 아님
~/Transcribe/inbox/회의/asr-multitrack/회의록.m4a                  # 세션 폴더 없이 파일을 바로 넣음
~/Transcribe/inbox/회의/asr-multitrack/2026-09-08/원본/김철수.m4a  # 세션 폴더 아래에 또 폴더
```

The comments, in order: the second folder is not a mode name; the file sits
directly in the mode folder with no session folder; there is another folder under
the session folder.

Only the folder structure sets the mode. You cannot set a default such as "this
category is always diarize". Each file's mode comes from the path it is in.

The daemon does not watch any folder outside `~/Transcribe/inbox/`, including
sibling folders such as `~/Transcribe/archive/` (where originals are kept). You
can keep other files there, such as downloaded models (`~/Transcribe/model/` and
so on). Hidden files, whose names start with `.`, are ignored wherever they are.
