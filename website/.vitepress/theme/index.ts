import type { Theme } from 'vitepress'
import DefaultTheme from 'vitepress/theme-without-fonts'
import '@fontsource-variable/newsreader/opsz.css'
import '@fontsource-variable/newsreader/opsz-italic.css'
import '@fontsource-variable/inter/wght.css'
import '@fontsource-variable/jetbrains-mono/wght.css'
import Landing from './components/Landing.vue'
import './custom.css'
import './landing.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Landing', Landing)
  },
} satisfies Theme
