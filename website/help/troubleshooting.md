# Troubleshooting

## The daemon won't start

This is the case where you copied the plist to `~/Library/LaunchAgents/` and ran `launchctl load`, but the process is still not running. First check whether it is running:

```sh
launchctl list | grep transcribe-inbox
```

If the first column is a PID, it is running; if it is `-`, it is not running (the second column is the last exit code).

- When launchd fails to launch (a wrong binary path, etc.), **both** `~/Library/Logs/transcribe-inbox.log` and `~/Library/Logs/transcribe-inbox.error.log` are **empty**. This is because the Python process itself could not start and so had nothing to write.
- If both logs are empty and the daemon is not running, the most likely cause is a wrong absolute path in the plist (`uv`, `whisper-cli`, the model files, etc.). Re-check them one by one with `which`/`ls`.
- After editing the plist, you must run `launchctl unload` and then `launchctl load` again. Just overwriting the file does not re-apply it.

For the detailed installation steps and each value, see [Installation](/getting-started/installation) and [Configuration](/reference/configuration).

## The session becomes FAILED

A common reason an `asr-multitrack` session becomes `FAILED` is that the session folder contains files other than the per-speaker audio (metadata such as `.txt` or `.dat`). Every non-hidden file in the session folder is registered as a track and fails when audio decoding is attempted. Keep only per-speaker audio files directly under the session folder. For details, including the caveat about tracks whose start times are misaligned, see [Modes](/guide/modes).

## A job became FAILED

When a job becomes `FAILED`, the error message is recorded in the DB, the original file stays in the inbox, and no transcript is published. A failed job is not retried automatically even when you restart the daemon, so after fixing the cause you must try again yourself with the `retry` command. For the status-check query and how to retry, see [Usage](/guide/usage).
