<script setup lang="ts">
import { computed } from 'vue';
import { Cog, Calculator, UserCircle } from 'lucide-vue-next';
import type { Agent } from '@/types';

const props = defineProps<{
  agent: Agent;
  size?: 'sm' | 'md' | 'lg';
}>();

// Size classes
const sizeClasses = computed(() => {
  switch (props.size ?? 'md') {
    case 'sm':
      return 'w-8 h-8';
    case 'lg':
      return 'w-14 h-14';
    default:
      return 'w-10 h-10';
  }
});

const iconSizeClasses = computed(() => {
  switch (props.size ?? 'md') {
    case 'sm':
      return 'w-4 h-4';
    case 'lg':
      return 'w-7 h-7';
    default:
      return 'w-5 h-5';
  }
});

// Background color based on role
const bgColorClass = computed(() => {
  switch (props.agent.role) {
    case 'system_designer':
      return 'bg-blue-500';
    case 'number_designer':
      return 'bg-green-500';
    case 'player_advocate':
      return 'bg-orange-500';
    case 'operations_analyst':
      return 'bg-purple-500';
    default:
      return 'bg-gray-500';
  }
});

// Status indicator color
const statusColorClass = computed(() => {
  switch (props.agent.status) {
    case 'speaking':
      return 'bg-green-400';
    case 'thinking':
      return 'bg-yellow-400 animate-pulse';
    case 'writing':
      return 'bg-indigo-400 animate-pulse';
    default:
      return 'bg-gray-400';
  }
});

// Icon component based on role
const iconComponent = computed(() => {
  switch (props.agent.role) {
    case 'system_designer':
      return Cog;
    case 'number_designer':
      return Calculator;
    case 'player_advocate':
      return UserCircle;
    default:
      return UserCircle;
  }
});

const hasAvatar = computed(() => Boolean(props.agent.avatarUrl));
</script>

<template>
  <div class="relative inline-flex">
    <!-- Avatar with icon -->
    <div
      :class="[
        'rounded-full flex items-center justify-center text-white overflow-hidden',
        sizeClasses,
        bgColorClass,
      ]"
    >
      <img
        v-if="hasAvatar"
        :src="agent.avatarUrl"
        :alt="agent.name"
        class="w-full h-full object-cover"
      />
      <component v-else :is="iconComponent" :class="iconSizeClasses" />
    </div>

    <!-- Status indicator -->
    <span
      :class="[
        'absolute bottom-0 right-0 block rounded-full ring-2 ring-white',
        statusColorClass,
        size === 'sm' ? 'w-2 h-2' : size === 'lg' ? 'w-4 h-4' : 'w-3 h-3',
      ]"
    />
  </div>
</template>
