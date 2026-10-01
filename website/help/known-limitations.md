# Known limitations

- whisper.cpp is not yet pinned to a specific git tag/commit — `brew install whisper-cpp` follows upstream's `stable` version as-is, so behavior may change without any particular warning in a later upgrade.
- The `diarize` mode has not yet undergone an end-to-end test against real recordings on this machine (`whisper-cli`/the models were not installed at development time) — the code path itself was fixed after reading the actual `whispermlx` library source, but it is a good idea to run one live smoke test before actually depending on it.
- If two *different* recordings end up with the same category+label (not a re-run of the same job, but a genuine file name collision), the transcript directory is overwritten. The original *audio* is designed to be protected against this (the content-hash suffix handling described in [Output & archive](/reference/output)), but the transcript itself currently is not.
- `HUGGINGFACE_TOKEN` currently has to be put directly into the (gitignored) plist file — fetching it from the macOS Keychain or a separate secrets file is not yet supported.
- The `미분류` (Uncategorized) folder name is hard-coded and does not change with the locale.
- Transcription language is currently fixed to Korean (`language="ko"` in the worker, `-l ko` for whisper.cpp); other languages cannot be configured yet.
