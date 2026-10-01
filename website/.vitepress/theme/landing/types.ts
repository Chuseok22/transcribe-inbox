/** Inline text: plain strings, inline code, or an internal/external link. */
export type RichSegment = string | { code: string } | { text: string; href: string }
export type RichText = readonly RichSegment[]

export interface ValuePoint {
  title: string
  body: RichText
}

export interface FlowStep {
  title: string
  body: string
  path?: string
}

export interface Mode {
  name: 'asr' | 'diarize' | 'asr-multitrack'
  description: string
}

export interface QuickStartStep {
  title: string
  body: RichText
}

export interface LandingContent {
  eyebrow: string
  /**
   * The two headline lines. A line given as several chunks keeps each chunk
   * on one line (used where CJK breaking would otherwise leave an orphan).
   */
  titleLines: readonly [readonly string[], readonly string[]]
  lede: RichText
  getStarted: string
  installHref: string
  platformNote: RichText
  copy: { idle: string; done: string; failed: string; label: string }

  demo: {
    label: string
    ariaLabel: string
    running: string
    complete: string
    caption: string
  }

  values: { title: string; intro: string; items: readonly ValuePoint[] }
  flow: { title: string; intro: string; steps: readonly FlowStep[]; modesLabel: string; modes: readonly Mode[] }
  quickStart: { title: string; intro: string; steps: readonly QuickStartStep[]; commandsLabel: string; next: RichText }
  privacy: { title: string; statement: string; facts: readonly string[] }
  closing: { title: string; note: RichText }
  footer: { license: string; languagesLabel: string }
}
