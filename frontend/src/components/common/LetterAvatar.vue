<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{
  name: string;
  size?: number;
  src?: string | null;
}>(), { size: 32 });

const COLORS = [
  '#4A90D9', '#7B68EE', '#E06C75', '#61AFEF', '#C678DD',
  '#56B6C2', '#D19A66', '#98C379', '#E5C07B', '#BE5046',
  '#3B82F6', '#8B5CF6', '#EC4899', '#14B8A6', '#F59E0B',
];

const letter = computed(() => {
  const n = props.name?.trim();
  if (!n) return '?';
  const last = n[n.length - 1];
  if (/[\u4e00-\u9fff]/.test(last)) return last;
  return n[0].toUpperCase();
});

const bgColor = computed(() => {
  let hash = 0;
  for (const ch of props.name || '') hash = ch.charCodeAt(0) + ((hash << 5) - hash);
  return COLORS[Math.abs(hash) % COLORS.length];
});
</script>

<template>
  <img v-if="src" :src="src" class="la-img" :style="{ width: size + 'px', height: size + 'px' }" />
  <div v-else class="la" :style="{ width: size + 'px', height: size + 'px', background: bgColor, fontSize: (size * 0.45) + 'px' }">
    {{ letter }}
  </div>
</template>

<style scoped>
.la { display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; color: #fff; font-weight: 600; flex-shrink: 0; user-select: none; }
.la-img { border-radius: 50%; object-fit: cover; flex-shrink: 0; }
</style>
