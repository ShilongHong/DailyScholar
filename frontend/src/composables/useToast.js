import { ref } from 'vue'

const messages = ref([])
let msgId = 0

export function useToast() {
  const showToast = (text, type = 'success') => {
    const id = ++msgId
    messages.value.push({ id, text, type })
    setTimeout(() => {
      messages.value = messages.value.filter(m => m.id !== id)
    }, 3000)
  }
  return { messages, showToast }
}
