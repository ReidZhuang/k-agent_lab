<template>
  <router-view />
  <DownloadOverlay />
</template>

<script setup>
import { provideDownloadStore } from './api/downloadStore.js'
import DownloadOverlay from './components/DownloadOverlay.vue'

provideDownloadStore()
</script>
