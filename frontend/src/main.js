import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@phosphor-icons/web/regular'
import '@phosphor-icons/web/fill'
import 'katex/dist/katex.min.css'
import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)
app.use(ElementPlus, { size: 'default' })
app.use(router)
app.mount('#app')
