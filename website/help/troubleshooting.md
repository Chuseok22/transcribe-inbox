# Troubleshooting

## The daemon does not start

You copied the plist to `~/Library/LaunchAgents/` and ran `launchctl load`, but no process is running. First check whether it is running.

```sh
launchctl list | grep transcribe-inbox
```

A PID in the first column means it is running. `-` means it is not. The second column is the last exit code.

- When launchd fails to start the process, for example because of a wrong `uv` path, both `~/Library/Logs/transcribe-inbox.log` and `~/Library/Logs/transcribe-inbox.error.log` are empty. The Python process never started, so it could not write a log.
- If both logs are empty and the daemon is not running, the most likely cause is a wrong absolute path in `ProgramArguments` (`uv` or the project path). Check each one with `which` or `ls`.
- After you edit the plist, run `launchctl unload` and then `launchctl load` again. Overwriting the file alone does not apply the change.
- A wrong `whisper-cli` or model path does not stop the daemon from starting. The daemon runs, the job ends as `FAILED`, and the error is in the log and in the error message recorded in the DB.

For the install steps and each value, see [Installation](/getting-started/installation) and [Configuration](/reference/configuration).

## A session ends up FAILED

A common reason an `asr-multitrack` session ends up `FAILED` is a file in the session folder that is not per-speaker audio, such as `.txt` or `.dat` metadata. Every file in the session folder except hidden files is registered as a track, so decoding such a file as audio fails. Keep only per-speaker audio files directly under the session folder. [Modes](/guide/modes) has the details, including what to watch for when track start times differ.

## A job ends up FAILED

When a job becomes `FAILED`, the error message is recorded in the DB. The original file stays in the inbox. A transcript is usually not saved, but it can already exist in the output folder if saving finished and only recording completion failed. Failed jobs are not retried automatically, even after a daemon restart. Fix the cause, then retry with the `retry` command. [Usage](/guide/usage) has the status queries and the retry steps.
