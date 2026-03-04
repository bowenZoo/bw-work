<script setup lang="ts">
import { onMounted } from 'vue';
import { useUserStore } from '@/stores/user';

const userStore = useUserStore();

onMounted(() => {
  userStore.init();
});
</script>

<template>
  <router-view />
</template>

<style scoped>
</style>
