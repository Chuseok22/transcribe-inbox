<script setup lang="ts">
import { withBase } from 'vitepress'
import type { RichText } from '../landing/types'

defineProps<{ segments: RichText }>()

const resolveHref = (href: string) => (href.startsWith('/') ? withBase(href) : href)
</script>

<template>
  <template v-for="(segment, index) in segments" :key="index">
    <template v-if="typeof segment === 'string'">{{ segment }}</template>
    <code v-else-if="'code' in segment">{{ segment.code }}</code>
    <a v-else :href="resolveHref(segment.href)">{{ segment.text }}</a>
  </template>
</template>
