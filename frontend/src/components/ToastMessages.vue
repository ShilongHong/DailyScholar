<template>
  <div class="fixed bottom-6 right-6 z-50 space-y-2">
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="animate-fade-in-up px-5 py-3 rounded-lg shadow-lg text-white text-sm font-medium flex items-center gap-2"
      :class="{
        'bg-green-500': msg.type === 'success',
        'bg-red-500': msg.type === 'error',
        'bg-blue-500': msg.type === 'info'
      }"
    >
      <i
        :class="[
          'text-lg',
          msg.type === 'success' ? 'ph-fill ph-check-circle' :
          msg.type === 'error' ? 'ph-fill ph-warning-circle' :
          'ph-fill ph-info'
        ]"
      ></i>
      {{ msg.text }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  messages: {
    type: Array,
    required: true
  }
})
</script>
