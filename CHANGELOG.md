# Changelog

**현재 버전:** 0.1.0  
**마지막 업데이트:** 2026-09-12T15:06:49Z  

---

## [0.1.0] - 2026-09-12

**✨ 기능**
- worker main loop with asr-multitrack support and job monitoring, retry CLI, launchd entrypoint
- watchdog wiring and startup reconciliation
- footprint/system metrics observation, background job monitor, notifications
- atomic transcript publish and source archiving
- job repository with idempotency, claim, and reconciliation queries
- job orchestration schema and backoff connection
- whispermlx engine adapter for mixed-speaker meetings
- whisper.cpp engine adapter
- timeline-preserving ffmpeg normalization
- markdown/txt/srt transcript formatters
- speaker-aware re-segmentation for mixed-speaker meetings
- canonical transcript schema and engine adapter interface
- file and folder stabilization checks
- source hashing for single files and multitrack sessions
- scaffold project and inbox path parsing

**🐛 수정**
- register moved multitrack sessions, revalidate before enqueue
- make retry's status transition atomic
- treat file vanishing mid-stat as unstable, not a crash
- clean up temp wav when ffmpeg invocation raises
- refresh moved job paths, roll back failed reconciliation
- guard reconciliation's recovery write against an aborted transaction
- close reconciliation crash-guard and shared-connection races
- build whispermlx transcript from one chronological word list
- atomic upsert for register_job; verify content hash before reuse
- archive_source never deletes/overwrites an existing destination
- pass numpy arrays (not paths) to whispermlx, add mps->cpu fallback
- cross-cutting review fixes from final whole-branch review
- strengthen skip guards in timeline regression tests to check model file existence
- notify before archiving on job completion, strengthen multitrack offset/sort test coverage
- category derivation, exception isolation, and race in watch service pending-session polling
- guard JobMonitor's swap-memory sampling against exceptions
- explicit UTF-8 encoding on transcript bundle writes
- close read-only transactions in job repository

**📝 문서**
- rewrite README with full setup and usage guide
- stop linking README to an untracked design spec
- add setup and usage README
- correct misleading SRT join comment

**✅ 테스트**
- fix model path env var names to match production
- anonymize example speaker name in test fixtures
- timeline regression fixtures for both engines' absolute timestamp preservation
- add exact-boundary regression test for pause threshold

**🔧 변경사항**
- stop tracking real plist, replaced by example template
- fix plist template placeholders and model path defaults
- harden gitignore against secret and scratch-path leaks
- expand .gitignore with standard Python/uv project entries
- track remaining empty test package __init__.py files
- untrack compiled bytecode and ignore __pycache__

---

## [0.0.2] - 2026-09-10

**🔧 변경사항**
- add project-auto-wizard ci/versioning scaffold
- Initial commit

---

