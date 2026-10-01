# 使用方法

## 工作方式

```
~/Transcribe/inbox/<카테고리>/[모드]/... 에 파일을 넣으면
  → watchdog이 파일을 감지하고, 크기 증가가 멈출 때까지 대기(안정화 확인)
  → PostgreSQL에 작업(job)으로 등록 (idempotent — 같은 내용의 파일은 절대 중복 큐잉되지 않음)
  → 워커가 작업을 하나씩 순차적으로 가져감 (GPU 작업 동시 실행 없음)
  → ffmpeg가 오디오를 16kHz mono WAV로 추출/리샘플링
    (오디오뿐 아니라 비디오 컨테이너에서도 동작 — "사전 준비물" 페이지의 "지원하는 입력 포맷" 참고;
    무음 구간을 절대 잘라내지 않으므로, 전사 결과의 타임스탬프는 항상 원본과 일치함)
  → 모드에 따라 엔진으로 라우팅:
      asr / asr-multitrack → whisper.cpp (단일 화자, 또는 사전 분리된 트랙)
      diarize               → whispermlx (다중 화자 회의, 화자 라벨 추가)
  → transcript.json(정본) + .md/.txt/.srt 파일을 Obsidian vault에 발행
  → 원본 파일은 아카이브로 이동, macOS 알림 발송
```

上面流程图的文字说明：把文件放入 `<카테고리>`（类别）/`[모드]`（模式）目录 → watchdog 检测并等待大小稳定 → 在 PostgreSQL 中登记为任务（幂等，内容相同的文件绝不会重复入队）→ worker 逐个顺序领取（不并发运行 GPU 任务）→ ffmpeg 提取/重采样为 16kHz mono WAV（音频和视频容器均适用；绝不裁剪静音，因此时间戳始终与原始文件一致）→ 按模式路由：asr / asr-multitrack 使用 whisper.cpp（单个说话人或预先分离的音轨），diarize 使用 whispermlx（多说话人会议，附加说话人标签）→ 将 transcript.json（正本）+ .md/.txt/.srt 发布到 Obsidian vault → 原始文件移入归档并发送 macOS 通知。

## 守护进程重启时

守护进程重启时（崩溃、重启电脑等），会在启动时自行对账状态：处理到一半卡住的任务会被重新放回队列（如果原始文件已不存在则标记为失败），转写已完成但尚未移入归档的任务会在此时被归档。

## 放入文件

在守护进程运行的状态下，只要按照[收件箱目录结构](/zh/guide/inbox-layout)复制或移动文件进去即可。没有需要另外运行的命令。不过登记的时间点因模式而异：

- `asr` / `diarize`：文件大小在 **5 秒**内不再增长，就视为复制已经结束，并登记为任务。
- `asr-multitrack`：会话文件夹内必须在 **60 秒**内没有任何变化才会登记。这是为了防止在逐个慢慢放入音轨的过程中，会话在不完整的状态下就被登记而设置的等待时间 — 放完所有音轨后请等待 1 分钟左右。

任务一次只处理一个，依次顺序处理（不会并发运行 GPU）。再次放入内容相同的文件也不会重复登记 — 因为是依据内容哈希而不是文件名来判定的，所以即使只改了名字再放入也是如此。


## 失败时

- 任务状态变为 `FAILED`，错误信息会记录到数据库。
- **原始文件会原样保留在收件箱中。** 既不会被移入归档，也不会被删除。转写结果不会被发布。
- 会弹出 macOS 通知 — 标题 `전사 실패`，正文 `<카테고리> · <원본 이름>: <에러 메시지>`。（标题含义为“转写失败”；正文为 `<类别> · <原始文件名>: <错误信息>`。）
- 失败的任务即使重启守护进程也**不会**自动重试。即使文件仍留在收件箱中，启动时的扫描也会认定“这个内容已经是失败的任务”而跳过 — 这是为了避免因为一个有问题的文件，在每次重启时都白白消耗数十分钟的 GPU。重试必须按下文所述显式进行。

## 查看状态

任务状态/历史保存在 PostgreSQL 中，而不是日志文件。状态值只有 `PENDING`（等待）、`PROCESSING`（处理中）、`COMPLETED`（完成）、`FAILED`（失败）这四种。

```sh
psql "$DATABASE_URL" -c "SELECT id, status, category, processing_mode, source_path, error_message, created_at FROM transcription_job ORDER BY created_at DESC LIMIT 10;"
```

只查看失败的任务：

```sh
psql "$DATABASE_URL" -c "SELECT id, source_path, error_code, error_message FROM transcription_job WHERE status = 'FAILED';"
```

`psql` 和下面的 `retry` 都要求**shell 中**存在 `DATABASE_URL` — 写入 plist 的值只对守护进程生效，因此在终端中需要另外执行 `export DATABASE_URL=...`。

## 重试

使用通过上述查询得到的任务 id 来执行（在项目目录中）：

```sh
uv run transcribe-inbox retry <job-id>
```

这个命令只是把任务状态从 `FAILED` 改回 `PENDING`，实际处理由守护进程在下一次轮询（约每 5 秒一次）时领取。必须**同时**满足两个条件，只要有一个不满足，就不会改动任何内容，而是输出错误信息后退出：

1. 该任务的状态必须是 `FAILED` — `PENDING`/`PROCESSING`/`COMPLETED` 会被拒绝。
2. 数据库中记录的原始路径下，文件（或会话文件夹）必须仍然存在 — 如果已把失败的原始文件移出收件箱或删除，就无法重试。

把文件暂时从收件箱中拿出来再放回去，也有同样的效果 — 即使内容相同，处于失败状态的任务也会重新入队。不过如果原因出在文件本身（损坏、不支持的编解码器等），无论重试多少次，结果都是一样的。
