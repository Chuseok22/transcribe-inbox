import type { LandingContent } from './types'

const installHref = '/zh/getting-started/installation'
const installGuide = { text: '安装文档', href: installHref }

export const zh: LandingContent = {
  eyebrow: 'macOS 后台转写守护进程',
  titleLines: [['把录音放进文件夹。'], ['转写稿会保存到', '你的笔记文件夹。']],
  lede: [
    'transcribe-inbox 会监视 ',
    { code: '~/Transcribe/inbox' },
    '。有新录音时，它在 Apple Silicon GPU 上完成转写，并把结果以普通文件保存到 Obsidian 库或你指定的文件夹。',
  ],
  getStarted: '开始使用',
  installHref,
  platformNote: ['这是第一条命令，其余步骤见', installGuide, '。'],
  copy: { idle: '复制', done: '已复制', failed: '复制失败', label: '复制命令' },

  demo: {
    label: '示例',
    ariaLabel: '示例：复制到 lectures 收件箱的 week2.m4a 被转写，transcript.md 等四个文件保存到笔记文件夹。',
    running: '正在 Apple Silicon GPU 上转写',
    complete: '完成，已保存 4 个文件。',
    caption: '示例输出。目前转写语言固定为韩语。',
  },

  values: {
    title: '功能',
    intro: '把录音复制到收件箱文件夹，转写稿就会出现在笔记文件夹里。不需要一直开着某个应用。',
    items: [
      {
        title: '本地转写',
        body: ['whisper.cpp 或 whispermlx 在 Apple Silicon GPU 上完成转写，不调用云端 API。'],
      },
      {
        title: '用目录结构配置',
        body: [
          '文件放在哪个路径，就按哪种方式处理。路径格式为 ',
          { code: 'inbox/<category>/[mode]/file' },
          '。第一层目录是分类，例如 ',
          { code: 'lectures' },
          ' 或 ',
          { code: 'meetings' },
          '。',
        ],
      },
      {
        title: '输出普通文件',
        body: [
          '每段录音生成 ',
          { code: 'transcript.json' },
          '、',
          { code: '.md' },
          '、',
          { code: '.txt' },
          ' 和 ',
          { code: '.srt' },
          ' 四个文件。输出目录可以是 Obsidian 库，也可以是任意文件夹。',
        ],
      },
      {
        title: '不做摘要',
        body: ['转写稿按识别结果原样保存，带时间戳。需要摘要时，用你自己的工具处理。'],
      },
    ],
  },

  flow: {
    title: '工作原理',
    intro: '守护进程由 launchd 启动，一次只处理一个任务。任务状态保存在数据库中，重启后可以接着处理。',
    steps: [
      { title: '放入', body: '把音频或视频文件复制到分类文件夹。', path: 'inbox/lectures/week2.m4a' },
      { title: '检测', body: '文件大小不再变化后加入队列。任务按内容哈希区分，同一个文件不会重复处理。' },
      { title: '转写', body: '根据模式，由 whisper.cpp 或 whispermlx 在 Apple Silicon GPU 上转写。' },
      {
        title: '保存',
        body: '四个转写文件保存到笔记文件夹，原文件移入归档目录，随后弹出 macOS 通知。',
        path: 'Transcripts/lectures/week2/',
      },
    ],
    modesLabel: '模式',
    modes: [
      { name: 'asr', description: '单人录音。没有模式文件夹时使用此模式。' },
      { name: 'diarize', description: '多人混在同一个文件里的录音，由 whispermlx 处理。' },
      { name: 'asr-multitrack', description: '每位说话人一个文件，放在同一个会话文件夹中。' },
    ],
  },

  quickStart: {
    title: '快速开始',
    intro: '安装共四步。这里的命令对应第一步。',
    steps: [
      { title: '安装工具', body: ['用 Homebrew 安装 ffmpeg 和 whisper.cpp，克隆仓库后运行 ', { code: 'uv sync' }, '。'] },
      { title: '准备数据库', body: ['创建数据库并导入表结构，任务状态保存在这里。'] },
      { title: '填写 plist', body: ['复制 plist 模板，填入收件箱、笔记文件夹和归档目录的路径。'] },
      { title: '加载守护进程', body: ['把 plist 复制到 ', { code: '~/Library/LaunchAgents' }, '，再用 ', { code: 'launchctl load' }, ' 加载。'] },
    ],
    commandsLabel: '第一步的命令',
    next: ['第二到第四步见', installGuide, '。'],
  },

  privacy: {
    title: '隐私',
    statement: 'transcribe-inbox 不会把录音或转写稿发送到任何地方。',
    facts: [
      '不调用云端 API，模型在本机运行。',
      '原文件移入本地归档文件夹。',
      '转写稿以普通文件保存在你指定的文件夹。',
      '以 MIT 许可证开源。',
    ],
  },

  closing: {
    title: '安装',
    note: ['仅支持 Apple Silicon 的 macOS。后续步骤见', installGuide, '。'],
  },

  footer: { license: 'MIT 许可证', languagesLabel: '语言' },
}
