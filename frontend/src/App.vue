<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-dialog-provider>
      <main class="app-shell">
        <section class="workspace">
          <header class="topbar">
            <div>
              <p class="eyebrow">blind-watermark</p>
              <h1>盲水印工作台</h1>
            </div>
            <n-tag :type="apiOnline ? 'success' : 'warning'" round>
              <template #icon>
                <n-icon :component="apiOnline ? CheckmarkCircleOutline : AlertCircleOutline" />
              </template>
              {{ apiOnline ? 'API 已连接' : '等待后端 API' }}
            </n-tag>
          </header>

          <n-tabs v-model:value="activeTab" type="segment" animated class="mode-tabs">
            <n-tab-pane name="embed" tab="嵌入水印">
              <div class="tool-grid">
                <section class="panel">
                  <div class="panel-title">
                    <n-icon :component="ImageOutline" />
                    <span>输入图片</span>
                  </div>
                  <div class="upload-grid">
                    <ImageUpload
                      label="原图"
                      description="需要写入水印的图片"
                      :file="embedForm.image"
                      @change="embedForm.image = $event"
                    />
                    <ImageUpload
                      label="水印图"
                      description="黑白图或透明 PNG 更容易提取"
                      :file="embedForm.watermark"
                      @change="embedForm.watermark = $event"
                    />
                  </div>
                </section>

                <section class="panel side-panel">
                  <div class="panel-title">
                    <n-icon :component="KeyOutline" />
                    <span>嵌入参数</span>
                  </div>
                  <n-form label-placement="top" :show-feedback="false">
                    <n-grid :cols="2" :x-gap="12" :y-gap="12" responsive="screen">
                      <n-form-item-gi label="图片密码">
                        <n-input-number v-model:value="embedForm.passwordImg" :min="0" />
                      </n-form-item-gi>
                      <n-form-item-gi label="水印密码">
                        <n-input-number v-model:value="embedForm.passwordWm" :min="0" />
                      </n-form-item-gi>
                      <n-form-item-gi label="输出格式" :span="2">
                        <n-select v-model:value="embedForm.outputFormat" :options="formatOptions" />
                      </n-form-item-gi>
                    </n-grid>
                  </n-form>
                  <div v-if="embedCapacityBits || watermarkBits" class="capacity-panel">
                    <div>
                      <span>原图容量</span>
                      <strong>{{ formatBits(embedCapacityBits) }}</strong>
                    </div>
                    <div>
                      <span>水印大小</span>
                      <strong :class="{ danger: isWatermarkOverflow }">{{ formatBits(watermarkBits) }}</strong>
                    </div>
                    <p v-if="isWatermarkOverflow">
                      水印图太大，当前原图最多建议使用 {{ maxWatermarkHint }} 以内的水印。
                    </p>
                  </div>
                  <n-button
                    type="primary"
                    size="large"
                    block
                    :loading="embedLoading"
                    :disabled="!canEmbed"
                    @click="handleEmbed"
                  >
                    <template #icon>
                      <n-icon :component="LockClosedOutline" />
                    </template>
                    生成带水印图片
                  </n-button>
                  <ResultPreview
                    v-if="embedResultUrl"
                    title="嵌入结果"
                    filename="embedded-watermark.png"
                    :src="embedResultUrl"
                  />
                </section>
              </div>
            </n-tab-pane>

            <n-tab-pane name="extract" tab="提取水印">
              <div class="tool-grid">
                <section class="panel">
                  <div class="panel-title">
                    <n-icon :component="ScanOutline" />
                    <span>待提取图片</span>
                  </div>
                  <ImageUpload
                    label="已嵌入水印的图片"
                    description="上传经过盲水印处理后的图片"
                    :file="extractForm.image"
                    @change="extractForm.image = $event"
                  />
                </section>

                <section class="panel side-panel">
                  <div class="panel-title">
                    <n-icon :component="OptionsOutline" />
                    <span>提取参数</span>
                  </div>
                  <n-form label-placement="top" :show-feedback="false">
                    <n-grid :cols="2" :x-gap="12" :y-gap="12" responsive="screen">
                      <n-form-item-gi label="图片密码">
                        <n-input-number v-model:value="extractForm.passwordImg" :min="0" />
                      </n-form-item-gi>
                      <n-form-item-gi label="水印密码">
                        <n-input-number v-model:value="extractForm.passwordWm" :min="0" />
                      </n-form-item-gi>
                      <n-form-item-gi label="水印宽度">
                        <n-input-number v-model:value="extractForm.width" :min="1" />
                      </n-form-item-gi>
                      <n-form-item-gi label="水印高度">
                        <n-input-number v-model:value="extractForm.height" :min="1" />
                      </n-form-item-gi>
                    </n-grid>
                  </n-form>
                  <n-button
                    type="primary"
                    size="large"
                    block
                    :loading="extractLoading"
                    :disabled="!canExtract"
                    @click="handleExtract"
                  >
                    <template #icon>
                      <n-icon :component="EyeOutline" />
                    </template>
                    提取水印图
                  </n-button>
                  <ResultPreview
                    v-if="extractResultUrl"
                    title="提取结果"
                    filename="extracted-watermark.png"
                    :src="extractResultUrl"
                  />
                </section>
              </div>
            </n-tab-pane>
          </n-tabs>
        </section>
      </main>
    </n-dialog-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import type { GlobalThemeOverrides, SelectOption } from 'naive-ui';
import {
  createDiscreteApi,
  NButton,
  NConfigProvider,
  NDialogProvider,
  NForm,
  NFormItemGi,
  NGrid,
  NIcon,
  NInputNumber,
  NSelect,
  NTabPane,
  NTabs,
  NTag
} from 'naive-ui';
import {
  AlertCircleOutline,
  CheckmarkCircleOutline,
  EyeOutline,
  ImageOutline,
  KeyOutline,
  LockClosedOutline,
  OptionsOutline,
  ScanOutline
} from '@vicons/ionicons5';
import ImageUpload from './components/ImageUpload.vue';
import ResultPreview from './components/ResultPreview.vue';
import { checkApiHealth, embedWatermark, extractWatermark } from './api';

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#0f766e',
    primaryColorHover: '#0d9488',
    primaryColorPressed: '#115e59',
    borderRadius: '8px',
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  }
};

const activeTab = ref<'embed' | 'extract'>('embed');
const apiOnline = ref(false);
const embedLoading = ref(false);
const extractLoading = ref(false);
const embedResultUrl = ref('');
const extractResultUrl = ref('');
const { message } = createDiscreteApi(['message']);
const embedImageSize = ref<ImageSize | null>(null);
const watermarkSize = ref<ImageSize | null>(null);

const formatOptions: SelectOption[] = [
  { label: 'PNG', value: 'png' },
  { label: 'JPG', value: 'jpg' }
];

const embedForm = reactive({
  image: null as File | null,
  watermark: null as File | null,
  passwordImg: 1,
  passwordWm: 1,
  outputFormat: 'png' as 'png' | 'jpg'
});

const extractForm = reactive({
  image: null as File | null,
  passwordImg: 1,
  passwordWm: 1,
  width: 128,
  height: 128
});

const embedCapacityBits = computed(() => {
  if (!embedImageSize.value) return 0;
  return Math.floor(embedImageSize.value.height / 8) * Math.floor(embedImageSize.value.width / 8);
});
const watermarkBits = computed(() => {
  if (!watermarkSize.value) return 0;
  return watermarkSize.value.width * watermarkSize.value.height;
});
const isWatermarkOverflow = computed(() => Boolean(watermarkBits.value && watermarkBits.value >= embedCapacityBits.value));
const maxWatermarkHint = computed(() => {
  if (!embedCapacityBits.value) return '-';
  const side = Math.floor(Math.sqrt(Math.max(embedCapacityBits.value - 1, 1)));
  return `${side} x ${side}`;
});
const canEmbed = computed(() => Boolean(embedForm.image && embedForm.watermark && !isWatermarkOverflow.value));
const canExtract = computed(() => Boolean(extractForm.image && extractForm.width > 0 && extractForm.height > 0));

onMounted(async () => {
  apiOnline.value = await checkApiHealth();
});

onBeforeUnmount(() => {
  revokeObjectUrl(embedResultUrl);
  revokeObjectUrl(extractResultUrl);
});

watch(
  () => embedForm.image,
  async (file) => {
    embedImageSize.value = file ? await getImageSize(file) : null;
  }
);

watch(
  () => embedForm.watermark,
  async (file) => {
    watermarkSize.value = file ? await getImageSize(file) : null;
  }
);

async function handleEmbed() {
  if (!embedForm.image || !embedForm.watermark) return;
  if (isWatermarkOverflow.value) {
    message.error(`水印图太大：${formatBits(watermarkBits.value)} > ${formatBits(embedCapacityBits.value)}`);
    return;
  }
  embedLoading.value = true;
  try {
    const blob = await embedWatermark({
      image: embedForm.image,
      watermark: embedForm.watermark,
      passwordImg: embedForm.passwordImg,
      passwordWm: embedForm.passwordWm,
      outputFormat: embedForm.outputFormat
    });
    replaceObjectUrl(embedResultUrl, blob);
    message.success('水印嵌入完成');
  } catch (error) {
    message.error(normalizeError(error));
  } finally {
    embedLoading.value = false;
  }
}

async function handleExtract() {
  if (!extractForm.image) return;
  extractLoading.value = true;
  try {
    const blob = await extractWatermark({
      image: extractForm.image,
      passwordImg: extractForm.passwordImg,
      passwordWm: extractForm.passwordWm,
      width: extractForm.width,
      height: extractForm.height
    });
    replaceObjectUrl(extractResultUrl, blob);
    message.success('水印提取完成');
  } catch (error) {
    message.error(normalizeError(error));
  } finally {
    extractLoading.value = false;
  }
}

function replaceObjectUrl(target: typeof embedResultUrl, blob: Blob) {
  revokeObjectUrl(target);
  target.value = URL.createObjectURL(blob);
}

function revokeObjectUrl(target: typeof embedResultUrl) {
  if (!target.value) return;
  URL.revokeObjectURL(target.value);
  target.value = '';
}

function normalizeError(error: unknown) {
  if (error instanceof Error) return error.message || '请求失败';
  return '请求失败';
}

function formatBits(bits: number) {
  if (!bits) return '-';
  return `${bits.toLocaleString()} bit`;
}

function getImageSize(file: File): Promise<ImageSize> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: image.naturalWidth, height: image.naturalHeight });
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('图片尺寸读取失败'));
    };
    image.src = url;
  });
}

type ImageSize = {
  width: number;
  height: number;
};
</script>
