<script setup lang="ts">
import { ref, computed } from 'vue';
import { Send } from 'lucide-vue-next';

const props = defineProps<{
  disabled?: boolean;
  placeholder?: string;
}>();

const emit = defineEmits<{
  submit: [topic: string];
}>();

const inputValue = ref('');

const isSubmitDisabled = computed(() => {
  return props.disabled || !inputValue.value.trim();
});

function handleSubmit() {
  if (isSubmitDisabled.value) return;

  const topic = inputValue.value.trim();
  if (topic) {
    emit('submit', topic);
    inputValue.value = '';
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleSubmit();
  }
}
</script>

<template>
  <div class="border-t border-gray-200 bg-white p-4">
    <div class="flex gap-3">
      <input
        v-model="inputValue"
        type="text"
        :placeholder="placeholder ?? 'Enter a discussion topic...'"
        :disabled="disabled"
        class="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
        @keydown="handleKeydown"
      />
      <button
        type="button"
        :disabled="isSubmitDisabled"
        class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        @click="handleSubmit"
      >
        <Send class="w-4 h-4" />
        <span>Start</span>
      </button>
    </div>
    <p v-if="disabled" class="mt-2 text-sm text-gray-500">
      Discussion in progress...
    </p>
  </div>
</template>
