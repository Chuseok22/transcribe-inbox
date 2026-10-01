# 使用方法

## 工作方式

```
~/Transcribe/inbox/<카테고리>/[모드]/... 에 파일을 넣으면
  → watchdog이 파일을 감지하고, 크기 증가가 멈출 때까지 대기(안정화 확인)
  → PostgreSQL에 작업(job)으로 등록 (같은 내용의 파일은 중복 등록되지 않음)
  → 워커가 작업을 하나씩 순차적으로 가져감 (GPU 작업 동시 실행 없음)
  → ffmpeg가 오디오를 16kHz mono WAV로 추출/리샘플링
    (비디오 컨테이너도 처리함. "사전 준비물" 페이지의 "지원하는 입력 포맷" 참고;
    무음 구간을 잘라내지 않으므로 전사 결과의 타임스탬프는 항상 원본과 일치함)
  → 모드에 따라 엔진으로 라우팅:
      asr / asr-multitrack → whisper.cpp (단일 화자, 또는 사전 분리된 트랙)
      diarize               → whispermlx (다중 화자 회의, 화자 라벨 추가)
  → transcript.json(정본) + .md/.txt/.srt 파일을 Obsidian vault에 저장
  → 원본 파일은 아카이브로 이동, macOS 알림 발송
```

流程图的大意如下：

1. 把文件放进 `~/Transcribe/inbox/<카테고리>/[모드]/...`（类别/模式）。
2. watchdog 检测到文件，等到文件大小不再增长。
3. 在 PostgreSQL 中登记为任务。内容相同的文件不会重复入队。
4. worker 逐个按顺序领取任务，不同时运行多个 GPU 任务。
5. ffmpeg 把音频提取并重采样为 16kHz mono WAV。视频容器同样适用（见“前置条件”页的“支持的输入格式”）。不裁剪静音片段，所以时间戳始终与原文件一致。
6. 按模式选择引擎：asr / asr-multitrack 用 whisper.cpp（单一说话人或预先分好的音轨），diarize 用 whispermlx（多说话人会议，附加说话人标签）。
7. 把 transcript.json（正本）和 .md/.txt/.srt 文件保存到 Obsidian vault。
8. 原文件移到归档，并发送 macOS 通知。

## 守护进程重启时

守护进程因崩溃、重启电脑等原因重新启动时，会在启动阶段重新校正任务状态。处理到一半中断的任务会重新放回队列，如果原文件已经不在，则标记为失败。转写已完成但还没移到归档的任务，会在这时归档。

## 放入文件

守护进程运行时，按照[收件箱目录结构](/zh/guide/inbox-layout)复制或移动文件进去即可，不需要另外执行命令。登记为任务的时间因模式而异。

- `asr` / `diarize`：文件大小 5 秒内不再增长，就认为复制已完成，登记为任务。
- `asr-multitrack`：会话文件夹 60 秒内没有任何变化才会登记。这段等待是为了避免在逐个放入音轨的过程中登记不完整的会话。放完所有音轨后，请等 1 分钟左右。

任务一次处理一个，按顺序进行，不会同时运行多个 GPU 任务。内容相同的文件再次放入也不会重复登记。程序按内容哈希而不是文件名判断，所以只改文件名再放入也一样。

## 失败时

- 任务状态变为 `FAILED`，错误信息记录到数据库。
- 原文件留在收件箱中，不会移到归档或被删除，也不会保存转写结果。
- 会弹出 macOS 通知。标题为 `전사 실패`（转写失败），正文为 `<카테고리> · <원본 이름>: <에러 메시지>`（类别 · 原文件名: 错误信息）。
- 失败的任务在守护进程重启后**不会自动重试**。即使文件还在收件箱中，启动时的扫描也会把它视为“已失败的任务”而跳过。这样可以避免因为一个有问题的文件，每次重启都占用 GPU 几十分钟。请按下面的方法手动重试。

## 查看状态

任务状态和历史保存在 PostgreSQL 中，不在日志文件里。状态值有 `PENDING`（等待）、`PROCESSING`（处理中）、`COMPLETED`（完成）、`FAILED`（失败）四种。

```sh
psql "$DATABASE_URL" -c "SELECT id, status, category, processing_mode, source_path, error_message, created_at FROM transcription_job ORDER BY created_at DESC LIMIT 10;"
```

只查看失败的任务：

```sh
psql "$DATABASE_URL" -c "SELECT id, source_path, error_code, error_message FROM transcription_job WHERE status = 'FAILED';"
```

使用 `psql` 和下面的 `retry` 命令时，shell 中需要有 `DATABASE_URL`。写在 plist 中的值只对守护进程生效，所以在终端中需要另外执行 `export DATABASE_URL=...`。

## 重试

在项目目录中执行下面的命令，填入用上面的查询找到的任务 id。

```sh
uv run transcribe-inbox retry <job-id>
```

这条命令只是把任务状态从 `FAILED` 改回 `PENDING`。实际处理由守护进程在下一次轮询（约每 5 秒一次）时领取。必须同时满足下面两个条件，只要有一个不满足，命令就不改动状态，输出错误信息后退出。

1. 任务状态必须是 `FAILED`。`PENDING`、`PROCESSING`、`COMPLETED` 状态会被拒绝。
2. 数据库中记录的原路径下，文件（或会话文件夹）必须还在。如果失败的原文件已被移出收件箱或删除，就无法重试。

把文件暂时从收件箱拿出来再放回去，效果相同。即使内容相同，失败过的任务也会重新入队。但如果问题出在文件本身（损坏、编解码器不受支持等），重试多少次结果都一样。
