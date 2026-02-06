<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { MessageSquare, Users, Zap, Paperclip, X, History, Radio, PlayCircle } from 'lucide-vue-next';
import api from '@/api';
import type { DiscussionStatus } from '@/types';

interface CurrentDiscussion {
  id: string;
  topic: string;
  status: DiscussionStatus;
  rounds: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

const router = useRouter();
const topicInput = ref('');
const attachmentFile = ref<File | null>(null);
const attachmentContent = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);

// Global discussion state
const currentDiscussion = ref<CurrentDiscussion | null>(null);
const isLoadingDiscussion = ref(false);
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null);

// Computed
const isDiscussionRunning = computed(() => currentDiscussion.value?.status === 'running');
const isDiscussionCompleted = computed(() => currentDiscussion.value?.status === 'completed');

// Fetch current discussion on mount
async function fetchCurrentDiscussion() {
  try {
    const response = await api.get<CurrentDiscussion | null>('/api/discussions/current');
    currentDiscussion.value = response.data;
  } catch (error) {
    console.error('Failed to fetch current discussion:', error);
    currentDiscussion.value = null;
  }
}

// Start polling for discussion status
function startPolling() {
  stopPolling();
  pollTimer.value = setInterval(fetchCurrentDiscussion, 5000);
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
}

// Navigate to join running discussion
function joinDiscussion() {
  router.push({ name: 'discussion' });
}

function startDiscussion() {
  if (topicInput.value.trim()) {
    // Store attachment in sessionStorage (URL has length limit)
    if (attachmentContent.value) {
      sessionStorage.setItem('discussion_attachment', JSON.stringify({
        filename: attachmentFile.value?.name || 'attachment.md',
        content: attachmentContent.value,
      }));
    } else {
      sessionStorage.removeItem('discussion_attachment');
    }

    // Navigate to discussion page with topic
    router.push({
      name: 'discussion',
      query: { topic: topicInput.value.trim() },
    });
  }
}

onMounted(() => {
  fetchCurrentDiscussion();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    startDiscussion();
  }
}

function triggerFileInput() {
  fileInputRef.value?.click();
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];

  if (file) {
    if (!file.name.endsWith('.md')) {
      alert('请上传 .md 格式的文件');
      return;
    }

    attachmentFile.value = file;

    try {
      attachmentContent.value = await file.text();
    } catch (error) {
      console.error('Failed to read file:', error);
      alert('读取文件失败');
      removeAttachment();
    }
  }
}

function removeAttachment() {
  attachmentFile.value = null;
  attachmentContent.value = '';
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col">
    <!-- Header -->
    <header class="p-6">
      <div class="max-w-4xl mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-gray-900 rounded-md flex items-center justify-center">
            <span class="text-white font-bold text-sm">BW</span>
          </div>
          <h1 class="text-xl font-semibold text-gray-900">Game Design</h1>
        </div>
        <router-link
          to="/history"
          class="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-white/50 rounded-lg transition-colors"
        >
          <History class="w-5 h-5" />
          <span>历史记录</span>
        </router-link>
      </div>
    </header>

    <!-- Main content -->
    <main class="flex-1 flex items-center justify-center p-6">
      <div class="max-w-2xl w-full">
        <!-- Hero section -->
        <div class="text-center mb-12">
          <h2 class="text-4xl font-bold text-gray-900 mb-4">
            AI 驱动的游戏设计讨论
          </h2>
          <p class="text-lg text-gray-600">
            与 AI 策划团队开启讨论。系统策划、数值策划和玩家代言人将协作帮助你设计游戏功能。
          </p>
        </div>

        <!-- Current discussion status -->
        <div v-if="isDiscussionRunning" class="bg-white rounded-2xl shadow-xl p-8 mb-6 border-l-4 border-green-500">
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <Radio class="w-6 h-6 text-green-500 animate-pulse" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-medium rounded">进行中</span>
              </div>
              <h3 class="text-lg font-semibold text-gray-900 mb-1">{{ currentDiscussion?.topic }}</h3>
              <p class="text-sm text-gray-600 mb-4">有一个讨论正在进行中，点击加入查看实时进展</p>
              <button
                type="button"
                class="flex items-center gap-2 px-6 py-2.5 bg-green-500 text-white rounded-lg hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-colors font-medium"
                @click="joinDiscussion"
              >
                <PlayCircle class="w-5 h-5" />
                <span>加入讨论</span>
              </button>
            </div>
          </div>
        </div>

        <div v-else-if="isDiscussionCompleted && currentDiscussion" class="bg-white rounded-2xl shadow-xl p-8 mb-6 border-l-4 border-gray-300">
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <MessageSquare class="w-6 h-6 text-gray-500" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs font-medium rounded">已结束</span>
              </div>
              <h3 class="text-lg font-semibold text-gray-900 mb-1">{{ currentDiscussion.topic }}</h3>
              <p class="text-sm text-gray-600">上一个讨论已结束，可以查看回放或开始新讨论</p>
            </div>
          </div>
        </div>

        <!-- Input section -->
        <div class="bg-white rounded-2xl shadow-xl p-8 mb-12">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            你想讨论什么？
          </label>
          <div class="flex gap-3">
            <input
              v-model="topicInput"
              type="text"
              placeholder="例如：为 RPG 游戏设计抽卡系统"
              class="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              @keydown="handleKeydown"
            />
            <button
              type="button"
              :disabled="!topicInput.trim()"
              class="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
              @click="startDiscussion"
            >
              开始讨论
            </button>
          </div>

          <!-- Attachment section -->
          <div class="mt-4">
            <input
              ref="fileInputRef"
              type="file"
              accept=".md"
              class="hidden"
              @change="handleFileSelect"
            />

            <div v-if="attachmentFile" class="flex items-center gap-2 p-3 bg-blue-50 rounded-lg">
              <Paperclip class="w-4 h-4 text-blue-500" />
              <span class="text-sm text-gray-700 flex-1">{{ attachmentFile.name }}</span>
              <span class="text-xs text-gray-500">{{ (attachmentFile.size / 1024).toFixed(1) }} KB</span>
              <button
                type="button"
                class="p-1 hover:bg-blue-100 rounded transition-colors"
                @click="removeAttachment"
              >
                <X class="w-4 h-4 text-gray-500" />
              </button>
            </div>

            <button
              v-else
              type="button"
              class="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-500 transition-colors"
              @click="triggerFileInput"
            >
              <Paperclip class="w-4 h-4" />
              <span>添加附件（.md 文件）</span>
            </button>
          </div>
        </div>

        <!-- Features -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-white rounded-xl p-6 shadow-md">
            <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
              <Users class="w-6 h-6 text-blue-500" />
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">多元视角</h3>
            <p class="text-sm text-gray-600">
              获取系统策划、数值策划和玩家代言人的专业意见。
            </p>
          </div>

          <div class="bg-white rounded-xl p-6 shadow-md">
            <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
              <MessageSquare class="w-6 h-6 text-green-500" />
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">实时讨论</h3>
            <p class="text-sm text-gray-600">
              观看 AI 团队讨论并迭代你的游戏设计创意。
            </p>
          </div>

          <div class="bg-white rounded-xl p-6 shadow-md">
            <div class="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mb-4">
              <Zap class="w-6 h-6 text-orange-500" />
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">即时结果</h3>
            <p class="text-sm text-gray-600">
              获得兼顾多方视角的综合设计方案。
            </p>
          </div>
        </div>
      </div>
    </main>

  </div>
</template>
