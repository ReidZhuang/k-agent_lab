<template>
  <router-view />
  <DownloadOverlay />
  <ChallengeOverlay />
</template>

<script setup>
import { provideDownloadStore } from './api/downloadStore.js'
import DownloadOverlay from './components/DownloadOverlay.vue'
import ChallengeOverlay from './components/ChallengeOverlay.vue'

provideDownloadStore()
</script>
