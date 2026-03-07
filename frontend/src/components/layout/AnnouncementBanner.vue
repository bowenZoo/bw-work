<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { CHANGELOG } from '@/data/changelog'

const STORAGE_KEY = 'bw_announcement_read_version'

const expanded = ref(false)
const readVersion = ref('')

const latestVersion = CHANGELOG[0]?.version ?? ''
const hasUnread = computed(() => readVersion.value !== latestVersion)

function dismiss() {
  readVersion.value = latestVersion
  localStorage.setItem(STORAGE_KEY, latestVersion)
}

function toggle() {
  expanded.value = !expanded.value
  if (expanded.value) {
    dismiss()
  }
}

const TYPE_CONFIG = {
  new:     { label: '新增', bg: '#dbeafe', color: '#1d4ed8' },
  fix:     { label: '修复', bg: '#dcfce7', color: '#15803d' },
  improve: { label: '优化', bg: '#fef9c3', color: '#a16207' },
  break:   { label: '变更', bg: '#fee2e2', color: '#b91c1c' },
}

onMounted(() => {
  readVersion.value = localStorage.getItem(STORAGE_KEY) || ''
})
</script>

<template>
  <div class="ann-wrap">
    <!-- Trigger button -->
    <button class="ann-trigger" @click="toggle" :class="{ 'ann-trigger--active': expanded }">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3z"/>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </svg>
      <span class="ann-label">更新公告</span>
      <span class="ann-version">{{ CHANGELOG[0]?.version }}</span>
      <span v-if="hasUnread" class="ann-dot"></span>
    </button>

    <!-- Dropdown panel -->
    <Transition name="ann-drop">
      <div v-if="expanded" class="ann-panel">
        <div class="ann-panel-header">
          <span class="ann-panel-title">版本更新记录</span>
          <button class="ann-close" @click="expanded = false">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <div class="ann-scroll">
          <div v-for="(entry, idx) in CHANGELOG" :key="entry.version" class="ann-entry">
            <!-- Version header -->
            <div class="ann-ver-head">
              <span class="ann-ver-badge" :class="{ 'ann-ver-latest': idx === 0 }">
                {{ entry.version }}
              </span>
              <span v-if="idx === 0" class="ann-latest-tag">最新</span>
              <span class="ann-date">{{ entry.date }}</span>
            </div>

            <!-- Items -->
            <ul class="ann-items">
              <li v-for="item in entry.items" :key="item.text" class="ann-item">
                <span
                  class="ann-type-tag"
                  :style="{ background: TYPE_CONFIG[item.type].bg, color: TYPE_CONFIG[item.type].color }"
                >{{ TYPE_CONFIG[item.type].label }}</span>
                <span class="ann-item-text">{{ item.text }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.ann-wrap {
  position: relative;
  display: inline-flex;
}

/* Trigger button */
.ann-trigger {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 12.5px;
  color: #374151;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  position: relative;
}
.ann-trigger:hover { background: #f9fafb; border-color: #d1d5db; }
.ann-trigger--active { background: #f0f9ff; border-color: #93c5fd; color: #1d4ed8; }

.ann-label { font-weight: 500; }

.ann-version {
  padding: 1px 6px;
  background: #f3f4f6;
  border-radius: 999px;
  font-size: 11px;
  color: #6b7280;
  font-family: monospace;
}
.ann-trigger--active .ann-version { background: #dbeafe; color: #1d4ed8; }

.ann-dot {
  position: absolute;
  top: -3px;
  right: -3px;
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
  border: 1.5px solid #fff;
}

/* Dropdown panel */
.ann-panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  width: 400px;
  max-height: 480px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  z-index: 200;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ann-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  flex-shrink: 0;
}
.ann-panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
}
.ann-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.12s;
}
.ann-close:hover { background: #f3f4f6; color: #374151; }

.ann-scroll {
  overflow-y: auto;
  flex: 1;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Version entry */
.ann-entry {}

.ann-ver-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
}
.ann-ver-badge {
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
  color: #374151;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 6px;
}
.ann-ver-latest {
  background: #111827;
  color: #fff;
}
.ann-latest-tag {
  font-size: 10px;
  font-weight: 700;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 1px 7px;
  border-radius: 999px;
  letter-spacing: 0.02em;
}
.ann-date {
  font-size: 11px;
  color: #9ca3af;
  margin-left: auto;
}

/* Items */
.ann-items {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.ann-item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  font-size: 12.5px;
  line-height: 1.5;
}
.ann-type-tag {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  margin-top: 1px;
  letter-spacing: 0.02em;
}
.ann-item-text {
  color: #374151;
}

/* Transition */
.ann-drop-enter-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.ann-drop-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}
.ann-drop-enter-from,
.ann-drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* Scrollbar */
.ann-scroll::-webkit-scrollbar { width: 4px; }
.ann-scroll::-webkit-scrollbar-track { background: transparent; }
.ann-scroll::-webkit-scrollbar-thumb { background: #e5e7eb; border-radius: 4px; }

@media (max-width: 640px) {
  .ann-panel { width: calc(100vw - 24px); left: 0; }
}
</style>
