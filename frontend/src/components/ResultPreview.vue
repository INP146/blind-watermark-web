<template>
  <div class="result-preview">
    <div class="result-header">
      <strong>{{ title }}</strong>
      <n-button text tag="a" :href="src" :download="filename">
        <template #icon>
          <n-icon :component="DownloadOutline" />
        </template>
        下载
      </n-button>
    </div>
    <img :src="src" :alt="title" />
  </div>
</template>

<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';
import { DownloadOutline } from '@vicons/ionicons5';

defineProps<{
  title: string;
  filename: string;
  src: string;
}>();
</script>
