<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

const props = defineProps<{
  text: string
  labels: { idle: string; done: string; failed: string; label: string }
}>()

type CopyState = 'idle' | 'done' | 'failed'
const RESET_AFTER_MS = 1800

const state = ref<CopyState>('idle')
let resetTimer: ReturnType<typeof setTimeout> | undefined

function copyWithTextarea(text: string): boolean {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    document.body.removeChild(textarea)
  }
}

async function writeToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      return copyWithTextarea(text)
    }
  }
  return copyWithTextarea(text)
}

async function copy() {
  const copied = await writeToClipboard(props.text)
  state.value = copied ? 'done' : 'failed'
  clearTimeout(resetTimer)
  resetTimer = setTimeout(() => (state.value = 'idle'), RESET_AFTER_MS)
}

onBeforeUnmount(() => clearTimeout(resetTimer))
</script>

<template>
  <button type="button" class="ti-copy" :data-state="state" :aria-label="`${labels.label}: ${text}`" @click="copy">
    <span aria-live="polite">{{ labels[state] }}</span>
  </button>
</template>
