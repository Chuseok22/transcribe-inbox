<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { LandingContent } from '../landing/types'

defineProps<{ demo: LandingContent['demo'] }>()

/*
 * The card plays once: the progress bar fills, then transcript lines and the
 * file list appear one by one, then the status turns to "done".
 * SSR renders the 'pending' phase; CSS hides the not-yet-revealed parts only
 * when JS is present and the reader has not asked for reduced motion.
 */
type Phase = 'pending' | 'playing' | 'done'

const TRANSCRIPT_LINES = [
  { time: '00:00:04', text: '지난 시간에 이어서 오늘은 정렬 알고리즘을 봅니다.' },
  { time: '00:00:11', text: '먼저 삽입 정렬부터 손으로 따라가 볼게요.' },
  { time: '00:00:19', text: '배열이 거의 정렬돼 있으면 꽤 빠르게 끝납니다.' },
  { time: '00:00:27', text: '그럼 최악의 경우는 언제일까요?' },
] as const
const OUTPUT_FILES = ['transcript.json', 'transcript.md', 'transcript.txt', 'transcript.srt'] as const
const WAVE_HEIGHTS = [
  30, 55, 40, 70, 90, 60, 45, 80, 100, 65, 35, 50, 75, 95, 70, 40, 30, 60, 85, 55, 45, 70, 90, 50, 35, 65, 80, 45,
  30, 55, 75, 60, 40, 85, 70, 50,
] as const

const FIRST_REVEAL_MS = 1900
const REVEAL_STEP_MS = 650
const REVEAL_COUNT = TRANSCRIPT_LINES.length + 1 // lines + file list

const phase = ref<Phase>('pending')
const revealed = ref(0)
const timers: ReturnType<typeof setTimeout>[] = []

function play() {
  phase.value = 'playing'
  for (let step = 1; step <= REVEAL_COUNT; step++) {
    timers.push(setTimeout(() => (revealed.value = step), FIRST_REVEAL_MS + (step - 1) * REVEAL_STEP_MS))
  }
  timers.push(setTimeout(() => (phase.value = 'done'), FIRST_REVEAL_MS + REVEAL_COUNT * REVEAL_STEP_MS))
}

onMounted(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    revealed.value = REVEAL_COUNT
    phase.value = 'done'
    return
  }
  // Two frames so the pending state is painted before the transition starts.
  requestAnimationFrame(() => requestAnimationFrame(play))
})

onBeforeUnmount(() => timers.forEach(clearTimeout))
</script>

<template>
  <figure class="ti-demo">
    <div class="ti-demo-stack" :class="`is-${phase}`" role="img" :aria-label="demo.ariaLabel">
      <div class="ti-card" aria-hidden="true">
        <div class="ti-card-head">
          <span class="ti-dots"><i /><i /><i /></span>
          <span class="ti-tag">{{ demo.label }}</span>
        </div>

        <div class="ti-drop">
          <div class="ti-path">~/Transcribe/inbox/<b>lectures</b>/</div>
          <div class="ti-file">
            <div class="ti-file-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M9 18V5l12-2v13" />
                <circle cx="6" cy="18" r="3" />
                <circle cx="18" cy="16" r="3" />
              </svg>
            </div>
            <div class="ti-file-body">
              <div class="ti-file-name">week2.m4a</div>
              <div class="ti-wave">
                <i
                  v-for="(height, index) in WAVE_HEIGHTS"
                  :key="index"
                  :style="{ height: `${height}%`, animationDelay: `${(index % 7) * 0.12}s` }"
                />
              </div>
            </div>
            <div class="ti-file-meta">01:12:40</div>
          </div>
          <div class="ti-progress"><i /></div>
        </div>

        <div class="ti-status">
          <span class="ti-pip" />
          <span v-if="phase === 'done'" class="ti-status-done">{{ demo.complete }}</span>
          <span v-else>{{ demo.running }}<span class="ti-ellipsis"><i>.</i><i>.</i><i>.</i></span></span>
        </div>

        <div class="ti-note">
          <div class="ti-note-path">~/Obsidian/second-brain/Transcripts/lectures/week2/</div>
          <div class="ti-note-title">transcript.md</div>
          <ol class="ti-lines" lang="ko">
            <li v-for="(line, index) in TRANSCRIPT_LINES" :key="line.time" :class="{ 'is-in': revealed > index }">
              <span class="ti-ts">[{{ line.time }}]</span>
              <span>speaker: {{ line.text }}</span>
            </li>
          </ol>
          <div class="ti-files" :class="{ 'is-in': revealed >= REVEAL_COUNT }">
            <span v-for="file in OUTPUT_FILES" :key="file">{{ file }}</span>
          </div>
        </div>
      </div>
    </div>
    <figcaption class="ti-caption">{{ demo.caption }}</figcaption>
  </figure>
</template>
