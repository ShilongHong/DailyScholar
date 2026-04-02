<template>
  <div class="h-full">
    <vue3-pdf-app
      :pdf="pdfSrc"
      style="height: 100%"
      @pages-rendered="onPagesRendered"
    />
  </div>
</template>

<script setup>
import Vue3PdfApp from 'vue3-pdf-app'
import 'vue3-pdf-app/dist/icons/main.css'

const props = defineProps({
  pdfSrc: { type: String, required: true }
})

const emit = defineEmits(['loaded'])

const onPagesRendered = () => {
  emit('loaded')
}
</script>
