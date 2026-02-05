<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeft, FolderOpen } from 'lucide-vue-next';
import GddUploader from '@/components/project/GddUploader.vue';
import ModuleSelector from '@/components/project/ModuleSelector.vue';
import DiscussionProgress from '@/components/project/DiscussionProgress.vue';
import DesignDocPreview from '@/components/project/DesignDocPreview.vue';

interface Project {
  id: string;
  name: string;
  description?: string;
}

interface Module {
  id: string;
  name: string;
  description: string;
  keywords: string[];
  dependencies: string[];
  estimated_rounds: number;
}

interface ModuleProgress {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed';
  round?: number;
}

type Step = 'upload' | 'select' | 'discuss' | 'result';

const route = useRoute();
const router = useRouter();

const projectId = computed(() => route.params.id as string);
const project = ref<Project | null>(null);
const currentStep = ref<Step>('upload');

// GDD state
const gddId = ref<string | null>(null);
const gddStatus = ref<string>('');

// Modules state
const modules = ref<Module[]>([]);
const suggestedOrder = ref<string[]>([]);

// Discussion state
const discussionId = ref<string | null>(null);
const isRunning = ref(false);
const isPaused = ref(false);
const moduleProgress = ref<ModuleProgress[]>([]);
const totalModules = ref(0);
const completedModules = ref(0);
const currentModule = ref<string | undefined>();
const currentRound = ref(0);

// Result state
const designDocContent = ref<string>('');

const progressRef = ref<InstanceType<typeof DiscussionProgress> | null>(null);
let pollInterval: number | null = null;
let wsConnection: WebSocket | null = null;

async function loadProject() {
  try {
    const response = await fetch(`/api/projects/${projectId.value}`);
    if (response.ok) {
      project.value = await response.json();
    } else {
      router.push('/');
    }
  } catch (error) {
    console.error('Failed to load project:', error);
    router.push('/');
  }
}

function handleGddUploaded(id: string, filename: string) {
  gddId.value = id;
  gddStatus.value = 'parsing';
  pollGddStatus();
}

async function pollGddStatus() {
  if (!gddId.value || !projectId.value) return;

  try {
    const response = await fetch(`/api/projects/${projectId.value}/gdd/${gddId.value}/modules`);
    if (response.ok) {
      const data = await response.json();
      gddStatus.value = data.status;

      if (data.status === 'ready') {
        modules.value = data.modules;
        suggestedOrder.value = data.suggested_order;
        currentStep.value = 'select';
      } else if (data.status === 'error') {
        // Handle error
      } else {
        // Still processing, poll again
        setTimeout(pollGddStatus, 2000);
      }
    }
  } catch (error) {
    console.error('Failed to poll GDD status:', error);
  }
}

async function handleStartDiscussion(selectedModules: string[], order: string[]) {
  if (!projectId.value || !gddId.value) return;

  try {
    const response = await fetch(`/api/projects/${projectId.value}/discussions/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gdd_id: gddId.value,
        modules: selectedModules,
        order,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      discussionId.value = data.discussion_id;
      isRunning.value = true;
      currentStep.value = 'discuss';

      // Initialize module progress
      moduleProgress.value = selectedModules.map((id) => ({
        id,
        name: modules.value.find((m) => m.id === id)?.name || id,
        status: 'pending' as const,
      }));
      totalModules.value = selectedModules.length;

      // Connect WebSocket
      connectWebSocket();

      // Start polling status
      startStatusPolling();
    }
  } catch (error) {
    console.error('Failed to start discussion:', error);
  }
}

function connectWebSocket() {
  if (!projectId.value) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/projects/${projectId.value}`;

  wsConnection = new WebSocket(wsUrl);

  wsConnection.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      handleWsMessage(message);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  };

  wsConnection.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  wsConnection.onclose = () => {
    // Reconnect if still running
    if (isRunning.value && !isPaused.value) {
      setTimeout(connectWebSocket, 3000);
    }
  };
}

function handleWsMessage(message: any) {
  switch (message.type) {
    case 'module_discussion_start':
      currentModule.value = message.module_id;
      updateModuleStatus(message.module_id, 'running');
      break;

    case 'module_discussion_progress':
      currentRound.value = message.round;
      if (progressRef.value) {
        progressRef.value.addMessage(message.speaker, message.summary);
      }
      break;

    case 'module_discussion_complete':
      updateModuleStatus(message.module_id, 'completed');
      completedModules.value++;
      break;

    case 'project_discussion_complete':
      isRunning.value = false;
      currentStep.value = 'result';
      loadDesignIndex();
      break;

    case 'discussion_paused':
      isPaused.value = true;
      isRunning.value = false;
      break;
  }
}

function updateModuleStatus(moduleId: string, status: ModuleProgress['status']) {
  const module = moduleProgress.value.find((m) => m.id === moduleId);
  if (module) {
    module.status = status;
    if (status === 'running') {
      module.round = currentRound.value;
    }
  }
}

function startStatusPolling() {
  pollInterval = window.setInterval(async () => {
    if (!discussionId.value || !projectId.value) return;

    try {
      const response = await fetch(
        `/api/projects/${projectId.value}/discussions/${discussionId.value}`
      );
      if (response.ok) {
        const data = await response.json();
        completedModules.value = data.progress.completed_modules;
        currentModule.value = data.progress.current_module;
        currentRound.value = data.progress.current_round;

        if (data.status === 'completed') {
          isRunning.value = false;
          currentStep.value = 'result';
          stopStatusPolling();
        } else if (data.status === 'paused') {
          isPaused.value = true;
        }
      }
    } catch (error) {
      console.error('Failed to poll status:', error);
    }
  }, 3000);
}

function stopStatusPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function handlePause() {
  if (!discussionId.value || !projectId.value) return;

  try {
    const response = await fetch(
      `/api/projects/${projectId.value}/discussions/${discussionId.value}/pause`,
      { method: 'POST' }
    );
    if (response.ok) {
      isPaused.value = true;
    }
  } catch (error) {
    console.error('Failed to pause:', error);
  }
}

async function handleResume() {
  if (!discussionId.value || !projectId.value) return;

  try {
    const response = await fetch(
      `/api/projects/${projectId.value}/discussions/${discussionId.value}/resume`,
      { method: 'POST' }
    );
    if (response.ok) {
      isPaused.value = false;
      isRunning.value = true;
    }
  } catch (error) {
    console.error('Failed to resume:', error);
  }
}

async function handleSkip() {
  if (!discussionId.value || !projectId.value) return;

  try {
    const response = await fetch(
      `/api/projects/${projectId.value}/discussions/${discussionId.value}/skip`,
      { method: 'POST' }
    );
    if (response.ok) {
      const data = await response.json();
      updateModuleStatus(data.skipped_module, 'skipped');
    }
  } catch (error) {
    console.error('Failed to skip:', error);
  }
}

async function loadDesignIndex() {
  if (!projectId.value) return;

  try {
    const response = await fetch(`/api/projects/${projectId.value}/design`);
    if (response.ok) {
      const data = await response.json();
      designDocContent.value = data.content;
    }
  } catch (error) {
    console.error('Failed to load design index:', error);
  }
}

async function handleExport(format: 'markdown' | 'pdf') {
  if (!projectId.value) return;

  window.open(`/api/projects/${projectId.value}/design/export?format=${format}`, '_blank');
}

onMounted(() => {
  loadProject();
});

onUnmounted(() => {
  stopStatusPolling();
  if (wsConnection) {
    wsConnection.close();
  }
});
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow-sm sticky top-0 z-10">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center gap-4">
        <button
          type="button"
          class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
          @click="router.push('/')"
        >
          <ArrowLeft class="w-5 h-5" />
        </button>
        <FolderOpen class="w-6 h-6 text-blue-500" />
        <div>
          <h1 class="text-xl font-semibold text-gray-900">
            {{ project?.name || '加载中...' }}
          </h1>
          <p v-if="project?.description" class="text-sm text-gray-500">
            {{ project.description }}
          </p>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-8">
      <!-- Step indicator -->
      <div class="mb-8">
        <div class="flex items-center justify-center gap-4">
          <div
            v-for="(step, index) in ['upload', 'select', 'discuss', 'result']"
            :key="step"
            class="flex items-center"
          >
            <div
              class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium"
              :class="{
                'bg-blue-500 text-white': currentStep === step,
                'bg-green-500 text-white':
                  ['upload', 'select', 'discuss', 'result'].indexOf(currentStep) > index,
                'bg-gray-200 text-gray-500':
                  ['upload', 'select', 'discuss', 'result'].indexOf(currentStep) < index,
              }"
            >
              {{ index + 1 }}
            </div>
            <span
              class="ml-2 text-sm"
              :class="{
                'text-blue-600 font-medium': currentStep === step,
                'text-gray-500': currentStep !== step,
              }"
            >
              {{
                step === 'upload'
                  ? 'GDD 上传'
                  : step === 'select'
                  ? '模块选择'
                  : step === 'discuss'
                  ? '讨论进行'
                  : '结果查看'
              }}
            </span>
            <div
              v-if="index < 3"
              class="w-16 h-0.5 mx-4"
              :class="{
                'bg-green-500':
                  ['upload', 'select', 'discuss', 'result'].indexOf(currentStep) > index,
                'bg-gray-200':
                  ['upload', 'select', 'discuss', 'result'].indexOf(currentStep) <= index,
              }"
            />
          </div>
        </div>
      </div>

      <!-- Step content -->
      <div class="bg-white rounded-lg shadow-sm p-6">
        <!-- Step 1: Upload GDD -->
        <div v-if="currentStep === 'upload'" class="max-w-xl mx-auto">
          <h2 class="text-lg font-medium text-gray-900 mb-4">上传 GDD 文档</h2>
          <p class="text-gray-500 mb-6">
            上传游戏设计文档 (GDD)，系统将自动识别其中的功能模块。
          </p>
          <GddUploader
            v-if="projectId"
            :project-id="projectId"
            @uploaded="handleGddUploaded"
            @error="(msg) => console.error(msg)"
          />
          <div v-if="gddStatus === 'parsing'" class="mt-4 text-center text-gray-500">
            <div class="animate-pulse">正在解析文档并识别模块...</div>
          </div>
        </div>

        <!-- Step 2: Select modules -->
        <div v-else-if="currentStep === 'select'" class="max-w-2xl mx-auto">
          <h2 class="text-lg font-medium text-gray-900 mb-4">选择并排序讨论模块</h2>
          <p class="text-gray-500 mb-6">
            选择要讨论的模块，并调整讨论顺序。系统会按顺序逐个进行讨论。
          </p>
          <ModuleSelector
            :modules="modules"
            :suggested-order="suggestedOrder"
            @start="handleStartDiscussion"
          />
        </div>

        <!-- Step 3: Discussion in progress -->
        <div v-else-if="currentStep === 'discuss'">
          <h2 class="text-lg font-medium text-gray-900 mb-4">讨论进行中</h2>
          <DiscussionProgress
            v-if="projectId && discussionId"
            ref="progressRef"
            :project-id="projectId"
            :discussion-id="discussionId"
            :modules="moduleProgress"
            :total-modules="totalModules"
            :completed-modules="completedModules"
            :current-module="currentModule"
            :current-round="currentRound"
            :is-running="isRunning"
            :is-paused="isPaused"
            @pause="handlePause"
            @resume="handleResume"
            @skip="handleSkip"
          />
        </div>

        <!-- Step 4: Results -->
        <div v-else-if="currentStep === 'result'" class="h-[600px]">
          <h2 class="text-lg font-medium text-gray-900 mb-4">策划案生成完成</h2>
          <DesignDocPreview
            v-if="projectId"
            :project-id="projectId"
            :content="designDocContent"
            @export="handleExport"
          />
        </div>
      </div>
    </main>
  </div>
</template>
