<script setup lang="ts">
import { ref, computed } from 'vue';
import { Upload, FileText, AlertCircle, CheckCircle2 } from 'lucide-vue-next';

const props = defineProps<{
  projectId: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  uploaded: [gddId: string, filename: string];
  error: [message: string];
}>();

const dragActive = ref(false);
const uploading = ref(false);
const uploadProgress = ref(0);
const selectedFile = ref<File | null>(null);
const uploadStatus = ref<'idle' | 'uploading' | 'success' | 'error'>('idle');
const errorMessage = ref('');

const supportedFormats = ['.md', '.markdown', '.pdf', '.docx'];
const maxFileSize = 10 * 1024 * 1024; // 10MB

const fileInputRef = ref<HTMLInputElement | null>(null);

const acceptFormats = computed(() => {
  return supportedFormats.join(',');
});

function handleDragEnter(e: DragEvent) {
  e.preventDefault();
  e.stopPropagation();
  if (!props.disabled) {
    dragActive.value = true;
  }
}

function handleDragLeave(e: DragEvent) {
  e.preventDefault();
  e.stopPropagation();
  dragActive.value = false;
}

function handleDragOver(e: DragEvent) {
  e.preventDefault();
  e.stopPropagation();
}

function handleDrop(e: DragEvent) {
  e.preventDefault();
  e.stopPropagation();
  dragActive.value = false;

  if (props.disabled) return;

  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    validateAndSetFile(files[0]);
  }
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    validateAndSetFile(input.files[0]);
  }
}

function validateAndSetFile(file: File) {
  errorMessage.value = '';
  uploadStatus.value = 'idle';

  // Check file extension
  const ext = '.' + file.name.split('.').pop()?.toLowerCase();
  if (!supportedFormats.includes(ext)) {
    errorMessage.value = `不支持的文件格式。支持的格式: ${supportedFormats.join(', ')}`;
    uploadStatus.value = 'error';
    return;
  }

  // Check file size
  if (file.size > maxFileSize) {
    errorMessage.value = `文件过大 (${(file.size / 1024 / 1024).toFixed(1)}MB)。最大支持 10MB`;
    uploadStatus.value = 'error';
    return;
  }

  selectedFile.value = file;
}

async function uploadFile() {
  if (!selectedFile.value || !props.projectId) return;

  uploading.value = true;
  uploadStatus.value = 'uploading';
  uploadProgress.value = 0;
  errorMessage.value = '';

  try {
    const formData = new FormData();
    formData.append('file', selectedFile.value);

    const response = await fetch(`/api/projects/${props.projectId}/gdd`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Upload failed');
    }

    const data = await response.json();
    uploadStatus.value = 'success';
    uploadProgress.value = 100;
    emit('uploaded', data.gdd_id, data.filename);
  } catch (error) {
    uploadStatus.value = 'error';
    errorMessage.value = error instanceof Error ? error.message : 'Upload failed';
    emit('error', errorMessage.value);
  } finally {
    uploading.value = false;
  }
}

function triggerFileInput() {
  fileInputRef.value?.click();
}

function clearFile() {
  selectedFile.value = null;
  uploadStatus.value = 'idle';
  errorMessage.value = '';
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
}
</script>

<template>
  <div class="w-full">
    <input
      ref="fileInputRef"
      type="file"
      :accept="acceptFormats"
      class="hidden"
      @change="handleFileSelect"
    />

    <!-- Drop zone -->
    <div
      class="border-2 border-dashed rounded-lg p-8 text-center transition-colors"
      :class="{
        'border-blue-400 bg-blue-50': dragActive,
        'border-gray-300 hover:border-gray-400': !dragActive && !disabled,
        'border-gray-200 bg-gray-50 cursor-not-allowed': disabled,
      }"
      @dragenter="handleDragEnter"
      @dragleave="handleDragLeave"
      @dragover="handleDragOver"
      @drop="handleDrop"
      @click="!disabled && !selectedFile && triggerFileInput()"
    >
      <div v-if="!selectedFile">
        <Upload class="w-12 h-12 mx-auto text-gray-400 mb-4" />
        <p class="text-lg font-medium text-gray-700 mb-2">
          拖拽 GDD 文档到此处
        </p>
        <p class="text-sm text-gray-500 mb-4">
          或点击选择文件
        </p>
        <p class="text-xs text-gray-400">
          支持 Markdown (.md)、PDF (.pdf)、Word (.docx)，最大 10MB
        </p>
      </div>

      <div v-else class="flex items-center justify-center gap-4">
        <FileText class="w-10 h-10 text-blue-500" />
        <div class="text-left">
          <p class="font-medium text-gray-700">{{ selectedFile.name }}</p>
          <p class="text-sm text-gray-500">
            {{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB
          </p>
        </div>
        <button
          v-if="uploadStatus !== 'uploading'"
          type="button"
          class="text-gray-400 hover:text-gray-600"
          @click.stop="clearFile"
        >
          &times;
        </button>
      </div>
    </div>

    <!-- Status messages -->
    <div v-if="errorMessage" class="mt-3 flex items-center gap-2 text-red-600">
      <AlertCircle class="w-4 h-4" />
      <span class="text-sm">{{ errorMessage }}</span>
    </div>

    <div v-if="uploadStatus === 'success'" class="mt-3 flex items-center gap-2 text-green-600">
      <CheckCircle2 class="w-4 h-4" />
      <span class="text-sm">文件上传成功，正在解析...</span>
    </div>

    <!-- Upload button -->
    <div v-if="selectedFile && uploadStatus !== 'success'" class="mt-4">
      <button
        type="button"
        :disabled="uploading || disabled"
        class="w-full py-2 px-4 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        @click="uploadFile"
      >
        <Upload v-if="!uploading" class="w-4 h-4" />
        <span v-if="uploading">上传中... {{ uploadProgress }}%</span>
        <span v-else>上传文档</span>
      </button>
    </div>
  </div>
</template>
