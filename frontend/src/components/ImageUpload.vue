<template>
  <div class="image-upload">
    <n-upload
      accept="image/*"
      :max="1"
      :default-upload="false"
      :show-file-list="false"
      @change="handleChange"
    >
      <n-upload-dragger>
        <div class="dropzone" :class="{ 'has-preview': previewUrl }">
          <img v-if="previewUrl" :src="previewUrl" :alt="label" />
          <div v-else class="empty-preview">
            <n-icon :component="CloudUploadOutline" />
            <span>{{ label }}</span>
          </div>
        </div>
      </n-upload-dragger>
    </n-upload>
    <div class="upload-meta">
      <strong>{{ label }}</strong>
      <span>{{ file ? file.name : description }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import type { UploadFileInfo } from 'naive-ui';
import { NIcon, NUpload, NUploadDragger } from 'naive-ui';
import { CloudUploadOutline } from '@vicons/ionicons5';

const props = defineProps<{
  label: string;
  description: string;
  file: File | null;
}>();

const emit = defineEmits<{
  change: [file: File | null];
}>();

const previewUrl = ref('');

watch(
  () => props.file,
  (file) => {
    if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = file ? URL.createObjectURL(file) : '';
  },
  { immediate: true }
);

function handleChange(options: { fileList: UploadFileInfo[] }) {
  const selected = options.fileList.at(-1)?.file ?? null;
  emit('change', selected);
}
</script>
