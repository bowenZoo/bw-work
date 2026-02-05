<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { GripVertical, ChevronRight, AlertTriangle, CheckCircle2 } from 'lucide-vue-next';

interface Module {
  id: string;
  name: string;
  description: string;
  keywords: string[];
  dependencies: string[];
  estimated_rounds: number;
}

const props = defineProps<{
  modules: Module[];
  suggestedOrder: string[];
  disabled?: boolean;
}>();

const emit = defineEmits<{
  start: [selectedModules: string[], order: string[]];
}>();

const selectedModules = ref<Set<string>>(new Set());
const moduleOrder = ref<string[]>([]);
const draggedModule = ref<string | null>(null);

// Initialize with suggested order
watch(
  () => props.suggestedOrder,
  (newOrder) => {
    if (newOrder.length > 0 && moduleOrder.value.length === 0) {
      moduleOrder.value = [...newOrder];
      // Select all by default
      selectedModules.value = new Set(newOrder);
    }
  },
  { immediate: true }
);

const moduleMap = computed(() => {
  return new Map(props.modules.map((m) => [m.id, m]));
});

const orderedModules = computed(() => {
  return moduleOrder.value
    .filter((id) => selectedModules.value.has(id))
    .map((id) => moduleMap.value.get(id))
    .filter(Boolean) as Module[];
});

const totalEstimatedTime = computed(() => {
  const rounds = orderedModules.value.reduce((sum, m) => sum + m.estimated_rounds, 0);
  // Assume ~5 minutes per round
  const minutes = rounds * 5;
  if (minutes < 60) return `${minutes} 分钟`;
  return `${(minutes / 60).toFixed(1)} 小时`;
});

const orderViolations = computed(() => {
  const violations: string[] = [];
  const discussed = new Set<string>();

  for (const moduleId of moduleOrder.value) {
    if (!selectedModules.value.has(moduleId)) continue;

    const module = moduleMap.value.get(moduleId);
    if (!module) continue;

    for (const dep of module.dependencies) {
      if (selectedModules.value.has(dep) && !discussed.has(dep)) {
        const depModule = moduleMap.value.get(dep);
        violations.push(
          `"${module.name}" 依赖 "${depModule?.name || dep}"，但 "${depModule?.name || dep}" 排在后面`
        );
      }
    }

    discussed.add(moduleId);
  }

  return violations;
});

const isOrderValid = computed(() => orderViolations.value.length === 0);

function toggleModule(moduleId: string) {
  if (props.disabled) return;

  if (selectedModules.value.has(moduleId)) {
    selectedModules.value.delete(moduleId);
  } else {
    selectedModules.value.add(moduleId);
    // Add to order if not already present
    if (!moduleOrder.value.includes(moduleId)) {
      moduleOrder.value.push(moduleId);
    }
  }
  // Trigger reactivity
  selectedModules.value = new Set(selectedModules.value);
}

function handleDragStart(moduleId: string) {
  draggedModule.value = moduleId;
}

function handleDragOver(e: DragEvent, targetId: string) {
  e.preventDefault();
  if (!draggedModule.value || draggedModule.value === targetId) return;

  const draggedIndex = moduleOrder.value.indexOf(draggedModule.value);
  const targetIndex = moduleOrder.value.indexOf(targetId);

  if (draggedIndex === -1 || targetIndex === -1) return;

  // Reorder
  moduleOrder.value.splice(draggedIndex, 1);
  moduleOrder.value.splice(targetIndex, 0, draggedModule.value);
}

function handleDragEnd() {
  draggedModule.value = null;
}

function selectAll() {
  selectedModules.value = new Set(props.modules.map((m) => m.id));
}

function selectNone() {
  selectedModules.value = new Set();
}

function autoSort() {
  // Topological sort based on dependencies
  const sorted: string[] = [];
  const visited = new Set<string>();
  const selected = Array.from(selectedModules.value);

  function visit(id: string) {
    if (visited.has(id)) return;
    visited.add(id);

    const module = moduleMap.value.get(id);
    if (module) {
      for (const dep of module.dependencies) {
        if (selectedModules.value.has(dep)) {
          visit(dep);
        }
      }
    }

    sorted.push(id);
  }

  for (const id of selected) {
    visit(id);
  }

  moduleOrder.value = sorted;
}

function handleStart() {
  if (!isOrderValid.value || selectedModules.value.size === 0) return;

  const selected = moduleOrder.value.filter((id) => selectedModules.value.has(id));
  emit('start', selected, selected);
}
</script>

<template>
  <div class="w-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-medium text-gray-900">
        选择讨论模块
      </h3>
      <div class="flex items-center gap-2 text-sm">
        <button
          type="button"
          class="text-blue-600 hover:text-blue-700"
          @click="selectAll"
        >
          全选
        </button>
        <span class="text-gray-300">|</span>
        <button
          type="button"
          class="text-blue-600 hover:text-blue-700"
          @click="selectNone"
        >
          取消全选
        </button>
        <span class="text-gray-300">|</span>
        <button
          type="button"
          class="text-blue-600 hover:text-blue-700"
          @click="autoSort"
        >
          自动排序
        </button>
      </div>
    </div>

    <!-- Module list -->
    <div class="space-y-2 mb-4">
      <div
        v-for="module in modules"
        :key="module.id"
        class="border rounded-lg p-3 cursor-pointer transition-colors"
        :class="{
          'border-blue-400 bg-blue-50': selectedModules.has(module.id),
          'border-gray-200 hover:border-gray-300': !selectedModules.has(module.id),
          'opacity-50': disabled,
        }"
        :draggable="selectedModules.has(module.id) && !disabled"
        @click="toggleModule(module.id)"
        @dragstart="handleDragStart(module.id)"
        @dragover="(e) => handleDragOver(e, module.id)"
        @dragend="handleDragEnd"
      >
        <div class="flex items-start gap-3">
          <!-- Drag handle -->
          <GripVertical
            v-if="selectedModules.has(module.id)"
            class="w-5 h-5 text-gray-400 cursor-grab flex-shrink-0 mt-0.5"
          />
          <div v-else class="w-5" />

          <!-- Checkbox -->
          <input
            type="checkbox"
            :checked="selectedModules.has(module.id)"
            class="mt-1 h-4 w-4 text-blue-600 rounded border-gray-300"
            @click.stop
            @change="toggleModule(module.id)"
          />

          <!-- Module info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-gray-900">{{ module.name }}</span>
              <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
                ~{{ module.estimated_rounds }} 轮
              </span>
            </div>
            <p class="text-sm text-gray-500 mt-1 line-clamp-2">
              {{ module.description }}
            </p>
            <div v-if="module.dependencies.length > 0" class="mt-2 flex items-center gap-1 text-xs text-gray-400">
              <span>依赖:</span>
              <span
                v-for="dep in module.dependencies"
                :key="dep"
                class="bg-gray-100 px-1.5 py-0.5 rounded"
              >
                {{ moduleMap.get(dep)?.name || dep }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Order preview -->
    <div v-if="orderedModules.length > 0" class="mb-4 p-4 bg-gray-50 rounded-lg">
      <h4 class="text-sm font-medium text-gray-700 mb-2">讨论顺序预览</h4>
      <div class="flex items-center flex-wrap gap-2">
        <template v-for="(module, index) in orderedModules" :key="module.id">
          <span class="text-sm bg-white px-2 py-1 rounded border">
            {{ index + 1 }}. {{ module.name }}
          </span>
          <ChevronRight v-if="index < orderedModules.length - 1" class="w-4 h-4 text-gray-400" />
        </template>
      </div>
      <div class="mt-2 text-sm text-gray-500">
        预计时长: {{ totalEstimatedTime }}
      </div>
    </div>

    <!-- Order validation -->
    <div v-if="orderViolations.length > 0" class="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
      <div class="flex items-start gap-2">
        <AlertTriangle class="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
        <div>
          <h4 class="text-sm font-medium text-yellow-800">依赖顺序问题</h4>
          <ul class="mt-1 text-sm text-yellow-700 list-disc list-inside">
            <li v-for="(violation, index) in orderViolations" :key="index">
              {{ violation }}
            </li>
          </ul>
          <button
            type="button"
            class="mt-2 text-sm text-yellow-700 underline hover:no-underline"
            @click="autoSort"
          >
            点击自动修复顺序
          </button>
        </div>
      </div>
    </div>

    <div v-else-if="selectedModules.size > 0" class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
      <div class="flex items-center gap-2 text-green-700">
        <CheckCircle2 class="w-5 h-5" />
        <span class="text-sm">讨论顺序符合依赖关系要求</span>
      </div>
    </div>

    <!-- Start button -->
    <button
      type="button"
      :disabled="disabled || selectedModules.size === 0 || !isOrderValid"
      class="w-full py-3 px-4 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
      @click="handleStart"
    >
      开始讨论 ({{ selectedModules.size }} 个模块)
    </button>
  </div>
</template>
