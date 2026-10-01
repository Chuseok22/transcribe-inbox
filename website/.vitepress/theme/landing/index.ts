import { en } from './en'
import { ko } from './ko'
import { zh } from './zh'
import type { LandingContent } from './types'

/** Keyed by VitePress `localeIndex` ('root' is English). */
export const landingByLocale: Readonly<Record<string, LandingContent>> = { root: en, ko, zh }

export const REPOSITORY_URL = 'https://github.com/Chuseok22/transcribe-inbox'

export const QUICK_START_COMMANDS = [
  'brew install ffmpeg whisper-cpp',
  'git clone https://github.com/Chuseok22/transcribe-inbox && cd transcribe-inbox',
  'uv sync',
] as const

export const LOCALE_LINKS = [
  { label: 'English', lang: 'en', href: '/' },
  { label: '한국어', lang: 'ko', href: '/ko/' },
  { label: '简体中文', lang: 'zh-CN', href: '/zh/' },
] as const
