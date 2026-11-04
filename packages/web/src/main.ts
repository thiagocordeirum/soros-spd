import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import { router } from './app/router/index.ts'
import '@fontsource-variable/red-hat-text/wght.css'
import './styles/motion.css'

createApp(App).use(router).mount('#app')
