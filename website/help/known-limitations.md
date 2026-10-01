# Known limitations

- whisper.cpp is not pinned to a specific git tag or commit yet.
  `brew install whisper-cpp` follows the upstream `stable` version, so a later
  upgrade can change behavior without warning.
- `diarize` mode has not had an end-to-end test with real recordings on this
  machine yet. `whisper-cli` and the models were not installed during
  development. The code path was corrected after reading the actual
  `whispermlx` library source, but run one live smoke test before you rely on
  this mode.
- If two different recordings end up with the same category and label, the
  transcript directory is overwritten. This means a real file name collision, not
  a re-run of the same job. The original audio is protected from this by the
  content-hash suffix described in [Output & archive](/reference/output).
  Transcripts are not protected yet.
- `HUGGINGFACE_TOKEN` currently has to go directly into the plist file, which is
  gitignored. Reading it from the macOS Keychain or a separate secrets file is
  not supported yet.
- The `미분류` (Uncategorized) folder name is hard-coded and does not change with
  the locale.
- The transcription language is fixed to Korean (`ko`). Other languages cannot
  be configured yet.
