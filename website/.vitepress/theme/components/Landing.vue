<script setup lang="ts">
import { computed } from 'vue'
import { useData, withBase } from 'vitepress'
import { landingByLocale, LOCALE_LINKS, QUICK_START_COMMANDS, REPOSITORY_URL } from '../landing'
import CopyButton from './CopyButton.vue'
import LandingDemo from './LandingDemo.vue'
import RichText from './RichText.vue'

const { localeIndex } = useData()
const content = computed(() => landingByLocale[localeIndex.value] ?? landingByLocale.root)
const installCommand = QUICK_START_COMMANDS[0]
</script>

<template>
  <main class="ti-landing" id="landing">
    <section class="ti-hero" aria-labelledby="ti-hero-title">
      <div class="ti-wrap ti-hero-grid">
        <div class="ti-hero-copy">
          <p class="ti-eyebrow">{{ content.eyebrow }}</p>
          <h1 id="ti-hero-title" class="ti-title">
            <span v-for="(line, lineIndex) in content.titleLines" :key="lineIndex" class="ti-title-line">
              <template v-if="line.length === 1">{{ line[0] }}</template>
              <template v-else>
                <span v-for="chunk in line" :key="chunk" class="ti-nowrap">{{ chunk }}</span>
              </template>
            </span>
          </h1>
          <p class="ti-lede"><RichText :segments="content.lede" /></p>
          <div class="ti-ctas">
            <a class="ti-btn ti-btn-primary" :href="withBase(content.installHref)">{{ content.getStarted }}</a>
            <a class="ti-btn ti-btn-ghost" :href="REPOSITORY_URL">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path
                  d="M12 .5a11.5 11.5 0 0 0-3.6 22.4c.6.1.8-.3.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0c2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.8.8 1.2 1.9 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A11.5 11.5 0 0 0 12 .5z"
                />
              </svg>
              GitHub
            </a>
          </div>
          <div class="ti-install">
            <div class="ti-install-box">
              <code><span class="ti-prompt" aria-hidden="true">$</span>{{ installCommand }}</code>
              <CopyButton :text="installCommand" :labels="content.copy" />
            </div>
            <p class="ti-platform"><RichText :segments="content.platformNote" /></p>
          </div>
          <div class="ti-notices"><slot /></div>
        </div>
        <LandingDemo :demo="content.demo" />
      </div>
    </section>

    <section class="ti-block" aria-labelledby="ti-values-title">
      <div class="ti-wrap">
        <div class="ti-section-head">
          <h2 id="ti-values-title">{{ content.values.title }}</h2>
          <p>{{ content.values.intro }}</p>
        </div>
        <ol class="ti-values">
          <li v-for="item in content.values.items" :key="item.title">
            <h3>{{ item.title }}</h3>
            <p><RichText :segments="item.body" /></p>
          </li>
        </ol>
      </div>
    </section>

    <section class="ti-block" aria-labelledby="ti-flow-title">
      <div class="ti-wrap">
        <div class="ti-section-head">
          <h2 id="ti-flow-title">{{ content.flow.title }}</h2>
          <p>{{ content.flow.intro }}</p>
        </div>
        <ol class="ti-flow">
          <li v-for="(step, index) in content.flow.steps" :key="step.title">
            <div class="ti-flow-mark" aria-hidden="true"><b>{{ index + 1 }}</b></div>
            <h3>{{ step.title }}</h3>
            <p>{{ step.body }}</p>
            <code v-if="step.path" class="ti-flow-path">{{ step.path }}</code>
          </li>
        </ol>
        <dl class="ti-modes" :aria-label="content.flow.modesLabel">
          <template v-for="mode in content.flow.modes" :key="mode.name">
            <dt>{{ mode.name }}</dt>
            <dd>{{ mode.description }}</dd>
          </template>
        </dl>
      </div>
    </section>

    <section class="ti-block" aria-labelledby="ti-qs-title">
      <div class="ti-wrap ti-qs">
        <div>
          <h2 id="ti-qs-title">{{ content.quickStart.title }}</h2>
          <p class="ti-qs-intro">{{ content.quickStart.intro }}</p>
          <ol class="ti-steps">
            <li v-for="step in content.quickStart.steps" :key="step.title">
              <div>
                <h3>{{ step.title }}</h3>
                <p><RichText :segments="step.body" /></p>
              </div>
            </li>
          </ol>
        </div>
        <div class="ti-term" role="group" :aria-label="content.quickStart.commandsLabel">
          <div v-for="command in QUICK_START_COMMANDS" :key="command" class="ti-term-row">
            <pre><span class="ti-prompt" aria-hidden="true">$ </span>{{ command }}</pre>
            <CopyButton :text="command" :labels="content.copy" />
          </div>
          <p class="ti-term-foot"><RichText :segments="content.quickStart.next" /></p>
        </div>
      </div>
    </section>

    <section class="ti-block ti-privacy" aria-labelledby="ti-privacy-title">
      <div class="ti-wrap ti-privacy-grid">
        <div>
          <h2 id="ti-privacy-title" class="ti-privacy-label">{{ content.privacy.title }}</h2>
          <p class="ti-privacy-statement">{{ content.privacy.statement }}</p>
        </div>
        <ul class="ti-facts">
          <li v-for="fact in content.privacy.facts" :key="fact">{{ fact }}</li>
        </ul>
      </div>
    </section>

    <section class="ti-block ti-closing" aria-labelledby="ti-close-title">
      <div class="ti-wrap ti-closing-grid">
        <h2 id="ti-close-title">{{ content.closing.title }}</h2>
        <div class="ti-install">
          <div class="ti-install-box">
            <code><span class="ti-prompt" aria-hidden="true">$</span>{{ installCommand }}</code>
            <CopyButton :text="installCommand" :labels="content.copy" />
          </div>
          <p class="ti-platform"><RichText :segments="content.closing.note" /></p>
        </div>
      </div>
    </section>
  </main>

  <footer class="ti-footer">
    <div class="ti-wrap ti-footer-row">
      <span>transcribe-inbox, {{ content.footer.license }}</span>
      <nav :aria-label="content.footer.languagesLabel">
        <a :href="REPOSITORY_URL">GitHub</a>
        <a v-for="locale in LOCALE_LINKS" :key="locale.href" :href="withBase(locale.href)" :lang="locale.lang">{{
          locale.label
        }}</a>
      </nav>
    </div>
  </footer>
</template>
