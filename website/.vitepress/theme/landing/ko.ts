import type { LandingContent } from './types'

const installHref = '/ko/getting-started/installation'
const installGuide = { text: '설치 문서', href: installHref }

export const ko: LandingContent = {
  eyebrow: 'macOS용 백그라운드 전사 데몬',
  titleLines: [['폴더에 녹음 파일을 넣으세요.'], ['전사본이 노트 폴더에 저장됩니다.']],
  lede: [
    'transcribe-inbox는 ',
    { code: '~/Transcribe/inbox' },
    ' 폴더를 지켜봅니다. 새 녹음이 들어오면 Apple Silicon GPU에서 전사하고, 결과를 Obsidian 볼트나 지정한 폴더에 일반 파일로 저장합니다.',
  ],
  getStarted: '시작하기',
  installHref,
  platformNote: ['첫 번째 명령입니다. 나머지 과정은 ', installGuide, '에 있습니다.'],
  copy: { idle: '복사', done: '복사됨', failed: '복사 실패', label: '명령 복사' },

  demo: {
    label: '예시',
    ariaLabel: '예시: lectures 인박스에 복사한 week2.m4a가 노트 폴더의 transcript.md 외 세 파일로 저장됩니다.',
    running: 'Apple Silicon GPU에서 전사 중',
    complete: '완료. 파일 4개를 저장했습니다.',
    caption: '예시 결과입니다. 전사 언어는 현재 한국어로 고정되어 있습니다.',
  },

  values: {
    title: '하는 일',
    intro: '녹음 파일을 인박스 폴더에 복사하면 전사본이 노트 폴더에 저장됩니다. 따로 열어 둘 앱은 없습니다.',
    items: [
      {
        title: '로컬에서 전사',
        body: ['whisper.cpp 또는 whispermlx가 Apple Silicon GPU에서 전사합니다. 클라우드 API는 호출하지 않습니다.'],
      },
      {
        title: '폴더 경로가 설정',
        body: [
          '파일을 넣은 경로로 처리 방식이 정해집니다. 형식은 ',
          { code: 'inbox/<category>/[mode]/file' },
          '입니다. 첫 번째 폴더가 카테고리이고, ',
          { code: 'lectures' },
          '나 ',
          { code: 'meetings' },
          '처럼 이름을 붙입니다.',
        ],
      },
      {
        title: '일반 파일로 저장',
        body: [
          '녹음 하나마다 ',
          { code: 'transcript.json' },
          ', ',
          { code: '.md' },
          ', ',
          { code: '.txt' },
          ', ',
          { code: '.srt' },
          ' 네 파일을 만듭니다. 저장 위치는 Obsidian 볼트여도 되고 일반 폴더여도 됩니다.',
        ],
      },
      {
        title: '요약하지 않음',
        body: ['인식한 내용을 타임스탬프와 함께 그대로 저장합니다. 요약이 필요하면 원하는 도구로 따로 합니다.'],
      },
    ],
  },

  flow: {
    title: '동작 방식',
    intro: '데몬은 launchd로 실행되고 작업을 한 번에 하나씩 처리합니다. 작업 상태는 데이터베이스에 저장되므로 재시작한 뒤에도 이어집니다.',
    steps: [
      { title: '넣기', body: '카테고리 폴더에 오디오나 영상 파일을 복사합니다.', path: 'inbox/lectures/week2.m4a' },
      {
        title: '감지',
        body: '파일 크기가 더 늘지 않으면 작업으로 등록합니다. 내용 해시로 구분하므로 같은 파일은 다시 처리하지 않습니다.',
      },
      { title: '전사', body: '모드에 따라 whisper.cpp 또는 whispermlx가 Apple Silicon GPU에서 전사합니다.' },
      {
        title: '저장',
        body: '전사본 네 파일을 노트 폴더에 저장하고, 원본을 아카이브로 옮긴 뒤 macOS 알림을 띄웁니다.',
        path: 'Transcripts/lectures/week2/',
      },
    ],
    modesLabel: '모드',
    modes: [
      { name: 'asr', description: '화자 한 명. 모드 폴더가 없으면 이 모드로 처리합니다.' },
      { name: 'diarize', description: '여러 화자가 한 파일에 섞인 녹음. whispermlx로 처리합니다.' },
      { name: 'asr-multitrack', description: '화자별로 나뉜 파일. 세션 폴더에 함께 넣습니다.' },
    ],
  },

  quickStart: {
    title: '빠른 시작',
    intro: '설치는 네 단계입니다. 여기 있는 명령은 첫 단계에 해당합니다.',
    steps: [
      { title: '도구 설치', body: ['Homebrew로 ffmpeg와 whisper.cpp를 설치하고, 저장소를 클론한 뒤 ', { code: 'uv sync' }, '를 실행합니다.'] },
      { title: '데이터베이스 준비', body: ['데이터베이스를 만들고 스키마를 적용합니다. 작업 상태가 여기에 저장됩니다.'] },
      { title: 'plist 작성', body: ['plist 템플릿을 복사하고 인박스, 노트 폴더, 아카이브 경로를 채웁니다.'] },
      { title: '데몬 등록', body: ['plist를 ', { code: '~/Library/LaunchAgents' }, '에 복사하고 ', { code: 'launchctl load' }, '로 등록합니다.'] },
    ],
    commandsLabel: '1단계 명령',
    next: ['2~4단계는 ', installGuide, '에 있습니다.'],
  },

  privacy: {
    title: '개인정보',
    statement: 'transcribe-inbox는 녹음이나 전사본을 외부로 보내지 않습니다.',
    facts: [
      '클라우드 API를 호출하지 않습니다. 모델은 Mac에서 실행됩니다.',
      '원본은 로컬 아카이브 폴더로 옮겨집니다.',
      '전사본은 지정한 폴더에 일반 파일로 저장됩니다.',
      'MIT 라이선스로 공개된 오픈 소스입니다.',
    ],
  },

  closing: {
    title: '설치',
    note: ['Apple Silicon Mac에서만 동작합니다. 이어지는 단계는 ', installGuide, '를 따르세요.'],
  },

  footer: { license: 'MIT 라이선스', languagesLabel: '언어' },
}
