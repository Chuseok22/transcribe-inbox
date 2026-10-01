import { defineConfig } from 'vitepress'

type Labels = {
  gettingStarted: string
  prerequisites: string
  installation: string
  guide: string
  inboxLayout: string
  modes: string
  usage: string
  reference: string
  configuration: string
  output: string
  help: string
  troubleshooting: string
  knownLimitations: string
}

const sidebarFor = (prefix: string, l: Labels) => [
  {
    text: l.gettingStarted,
    items: [
      { text: l.prerequisites, link: `${prefix}/getting-started/prerequisites` },
      { text: l.installation, link: `${prefix}/getting-started/installation` },
    ],
  },
  {
    text: l.guide,
    items: [
      { text: l.inboxLayout, link: `${prefix}/guide/inbox-layout` },
      { text: l.modes, link: `${prefix}/guide/modes` },
      { text: l.usage, link: `${prefix}/guide/usage` },
    ],
  },
  {
    text: l.reference,
    items: [
      { text: l.configuration, link: `${prefix}/reference/configuration` },
      { text: l.output, link: `${prefix}/reference/output` },
    ],
  },
  {
    text: l.help,
    items: [
      { text: l.troubleshooting, link: `${prefix}/help/troubleshooting` },
      { text: l.knownLimitations, link: `${prefix}/help/known-limitations` },
    ],
  },
]

const en: Labels = {
  gettingStarted: 'Getting started', prerequisites: 'Prerequisites', installation: 'Installation',
  guide: 'Guide', inboxLayout: 'Inbox layout', modes: 'Modes', usage: 'Usage',
  reference: 'Reference', configuration: 'Configuration', output: 'Output & archive',
  help: 'Help', troubleshooting: 'Troubleshooting', knownLimitations: 'Known limitations',
}
const ko: Labels = {
  gettingStarted: '시작하기', prerequisites: '사전 준비물', installation: '설치 및 설정',
  guide: '가이드', inboxLayout: '인박스 폴더 구조', modes: '지원하는 모드', usage: '사용법',
  reference: '레퍼런스', configuration: '설정', output: '결과물과 아카이브',
  help: '도움말', troubleshooting: '문제 해결', knownLimitations: '알려진 한계',
}
const zh: Labels = {
  gettingStarted: '快速上手', prerequisites: '前置条件', installation: '安装与配置',
  guide: '指南', inboxLayout: '收件箱目录结构', modes: '支持的模式', usage: '使用方法',
  reference: '参考', configuration: '配置', output: '输出与归档',
  help: '帮助', troubleshooting: '故障排查', knownLimitations: '已知限制',
}

export default defineConfig({
  title: 'transcribe-inbox',
  base: '/transcribe-inbox/',
  cleanUrls: true,
  lastUpdated: true,
  // Marks JS as available before first paint, so the landing demo can hide
  // the parts it is about to reveal without flashing them first.
  head: [['script', {}, "document.documentElement.classList.add('ti-js')"]],
  themeConfig: {
    socialLinks: [{ icon: 'github', link: 'https://github.com/Chuseok22/transcribe-inbox' }],
    search: { provider: 'local' },
  },
  locales: {
    root: {
      label: 'English',
      lang: 'en',
      description: 'Drop audio into a folder. Get a transcript in your notes. Fully local on Apple Silicon.',
      themeConfig: {
        nav: [{ text: 'Guide', link: '/getting-started/installation' }],
        sidebar: sidebarFor('', en),
      },
    },
    ko: {
      label: '한국어',
      lang: 'ko',
      link: '/ko/',
      description: '폴더에 녹음 파일을 넣으면 Apple Silicon Mac에서 로컬로 전사해 노트 폴더에 저장합니다.',
      themeConfig: {
        nav: [{ text: '가이드', link: '/ko/getting-started/installation' }],
        sidebar: sidebarFor('/ko', ko),
      },
    },
    zh: {
      label: '简体中文',
      lang: 'zh-CN',
      link: '/zh/',
      description: '把录音放进文件夹，在 Apple Silicon Mac 上本地转写，并保存到你的笔记文件夹。',
      themeConfig: {
        nav: [{ text: '指南', link: '/zh/getting-started/installation' }],
        sidebar: sidebarFor('/zh', zh),
      },
    },
  },
})
