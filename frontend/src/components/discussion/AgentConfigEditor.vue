<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ChevronDown, ChevronUp, RotateCcw, Settings2 } from 'lucide-vue-next';
import { getAvailableAgents } from '@/api/discussion';
import type { AgentConfig } from '@/types';

const props = defineProps<{
  agents: string[];
  configs: Record<string, Partial<AgentConfig>>;
}>();

const emit = defineEmits<{
  'update:agents': [agents: string[]];
  'update:configs': [configs: Record<string, Partial<AgentConfig>>];
}>();

// Default agent configs from API
const defaultConfigs = ref<Record<string, AgentConfig>>({});
const isLoadingDefaults = ref(false);

// All available agent roles (order matters for display)
const AGENT_ROLES = [
  { id: 'lead_planner', name: '主策划', emoji: '👔', locked: true },
  { id: 'system_designer', name: '系统策划', emoji: '⚙️', locked: false },
  { id: 'number_designer', name: '数值策划', emoji: '📊', locked: false },
  { id: 'player_advocate', name: '玩家代言人', emoji: '🎮', locked: false },
  { id: 'operations_analyst', name: '运营策划', emoji: '📈', locked: false },
  { id: 'visual_concept', name: '视觉概念', emoji: '🎨', locked: false },
];

// Currently selected agent for editing
const selectedAgentId = ref<string | null>(null);

// Show advanced editor
const showEditor = ref(false);

// Local copy of agents list
const localAgents = computed({
  get: () => props.agents,
  set: (val) => emit('update:agents', val),
});

// Local copy of configs
const localConfigs = computed({
  get: () => props.configs,
  set: (val) => emit('update:configs', val),
});

// Is a specific agent enabled?
function isAgentEnabled(agentId: string): boolean {
  const role = AGENT_ROLES.find(r => r.id === agentId);
  if (role?.locked) return true;
  return localAgents.value.length === 0 || localAgents.value.includes(agentId);
}

// Toggle agent on/off
function toggleAgent(agentId: string) {
  const role = AGENT_ROLES.find(r => r.id === agentId);
  if (role?.locked) return;

  const current = [...localAgents.value];
  if (current.length === 0) {
    // First toggle from "all enabled" mode — start with all except this one
    const allIds = AGENT_ROLES.filter(r => !r.locked).map(r => r.id);
    const without = allIds.filter(id => id !== agentId);
    emit('update:agents', ['lead_planner', ...without]);
  } else {
    const idx = current.indexOf(agentId);
    if (idx >= 0) {
      current.splice(idx, 1);
    } else {
      current.push(agentId);
    }
    emit('update:agents', current);
  }
}

// Get config for an agent (merged with defaults)
function getAgentConfig(agentId: string): AgentConfig {
  const defaults = defaultConfigs.value[agentId] || {
    role: '',
    goal: '',
    backstory: '',
    focus_areas: [],
  };
  const overrides = localConfigs.value[agentId] || {};
  return {
    ...defaults,
    ...overrides,
    focus_areas: overrides.focus_areas ?? defaults.focus_areas ?? [],
  };
}

// Update a config field
function updateConfigField(agentId: string, field: keyof AgentConfig, value: any) {
  const current = { ...localConfigs.value };
  if (!current[agentId]) {
    current[agentId] = {};
  }
  (current[agentId] as any)[field] = value;
  emit('update:configs', current);
}

// Reset agent config to defaults
function resetAgentConfig(agentId: string) {
  const current = { ...localConfigs.value };
  delete current[agentId];
  emit('update:configs', current);
}

// Has custom overrides?
function hasOverrides(agentId: string): boolean {
  return !!localConfigs.value[agentId] && Object.keys(localConfigs.value[agentId]).length > 0;
}

// Focus areas as comma-separated string
function getFocusAreasText(agentId: string): string {
  return getAgentConfig(agentId).focus_areas.join(', ');
}

function updateFocusAreas(agentId: string, text: string) {
  const areas = text.split(',').map(s => s.trim()).filter(Boolean);
  updateConfigField(agentId, 'focus_areas', areas);
}

function toggleEditor() {
  showEditor.value = !showEditor.value;
  if (showEditor.value && !selectedAgentId.value) {
    selectedAgentId.value = 'system_designer';
  }
}

// Fetch default configs from API
async function loadDefaults() {
  isLoadingDefaults.value = true;
  try {
    const result = await getAvailableAgents();
    defaultConfigs.value = result.agents;
  } catch {
    // Use empty defaults
  } finally {
    isLoadingDefaults.value = false;
  }
}

onMounted(() => {
  loadDefaults();
});
</script>

<template>
  <div class="agent-config-editor">
    <!-- Section label -->
    <label class="section-label">参与 Agent</label>

    <!-- Agent chips (always visible) -->
    <div class="agent-chips">
      <button
        v-for="role in AGENT_ROLES"
        :key="role.id"
        class="agent-chip"
        :class="{
          'is-active': isAgentEnabled(role.id),
          'is-locked': role.locked,
          'has-overrides': hasOverrides(role.id),
        }"
        @click="role.locked ? undefined : toggleAgent(role.id)"
        :title="role.locked ? '必选参与者' : (isAgentEnabled(role.id) ? '点击移除' : '点击添加')"
      >
        <span class="chip-emoji">{{ role.emoji }}</span>
        <span class="chip-name">{{ role.name }}</span>
        <span v-if="role.locked" class="chip-lock">必选</span>
        <span v-if="hasOverrides(role.id)" class="chip-dot" />
      </button>
    </div>

    <!-- Customize prompt toggle -->
    <button class="customize-toggle" @click="toggleEditor">
      <Settings2 class="customize-icon" />
      <span>自定义提示词</span>
      <component :is="showEditor ? ChevronUp : ChevronDown" class="toggle-arrow" />
    </button>

    <!-- Editor panel -->
    <div v-if="showEditor" class="editor-panel">
      <!-- Agent tabs -->
      <div class="editor-tabs">
        <button
          v-for="role in AGENT_ROLES"
          :key="role.id"
          class="editor-tab"
          :class="{
            'is-selected': selectedAgentId === role.id,
            'is-disabled': !isAgentEnabled(role.id),
          }"
          @click="selectedAgentId = role.id"
        >
          <span class="tab-emoji">{{ role.emoji }}</span>
          <span>{{ role.name }}</span>
          <span v-if="hasOverrides(role.id)" class="tab-dot" />
        </button>
      </div>

      <!-- Config form -->
      <div v-if="selectedAgentId" class="config-form">
        <div class="config-header">
          <button
            v-if="hasOverrides(selectedAgentId)"
            class="reset-btn"
            @click="resetAgentConfig(selectedAgentId!)"
            title="恢复默认"
          >
            <RotateCcw class="icon-xs" />
            <span>恢复默认</span>
          </button>
        </div>

        <div class="form-field">
          <label class="field-label">角色名称</label>
          <input
            type="text"
            class="field-input"
            :value="getAgentConfig(selectedAgentId).role"
            :placeholder="defaultConfigs[selectedAgentId]?.role || '角色名称'"
            @input="updateConfigField(selectedAgentId!, 'role', ($event.target as HTMLInputElement).value)"
          />
        </div>

        <div class="form-field">
          <label class="field-label">目标</label>
          <textarea
            class="field-textarea"
            rows="2"
            :value="getAgentConfig(selectedAgentId).goal"
            :placeholder="defaultConfigs[selectedAgentId]?.goal || '角色目标'"
            @input="updateConfigField(selectedAgentId!, 'goal', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>

        <div class="form-field">
          <label class="field-label">背景故事</label>
          <textarea
            class="field-textarea"
            rows="3"
            :value="getAgentConfig(selectedAgentId).backstory"
            :placeholder="defaultConfigs[selectedAgentId]?.backstory || '角色背景'"
            @input="updateConfigField(selectedAgentId!, 'backstory', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>

        <div class="form-field">
          <label class="field-label">关注领域</label>
          <input
            type="text"
            class="field-input"
            :value="getFocusAreasText(selectedAgentId)"
            placeholder="用逗号分隔，如: 战斗系统, 技能设计, 平衡性"
            @input="updateFocusAreas(selectedAgentId!, ($event.target as HTMLInputElement).value)"
          />
          <span class="field-hint">多个领域用逗号分隔</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-config-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #374151);
}

/* ===== Agent Chips ===== */
.agent-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.agent-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 20px;
  font-size: 13px;
  border: 1.5px solid var(--border-color, #e5e7eb);
  background: white;
  color: var(--text-secondary, #9ca3af);
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
}

.agent-chip:hover:not(.is-locked) {
  border-color: #d1d5db;
}

.agent-chip.is-active {
  border-color: var(--primary-color, #3b82f6);
  background: rgba(59, 130, 246, 0.06);
  color: var(--text-primary, #374151);
}

.agent-chip.is-locked {
  cursor: default;
  border-color: #d1d5db;
  background: #f9fafb;
  color: var(--text-primary, #374151);
}

.chip-emoji {
  font-size: 14px;
  line-height: 1;
}

.chip-name {
  font-weight: 500;
}

.chip-lock {
  font-size: 10px;
  padding: 0 4px;
  background: #e5e7eb;
  color: #6b7280;
  border-radius: 3px;
  line-height: 1.4;
}

.chip-dot {
  width: 6px;
  height: 6px;
  background: var(--primary-color, #3b82f6);
  border-radius: 50%;
  flex-shrink: 0;
}

/* ===== Customize Toggle ===== */
.customize-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 0;
  transition: color 0.15s;
  align-self: flex-start;
}

.customize-toggle:hover {
  color: var(--primary-color, #3b82f6);
}

.customize-icon {
  width: 13px;
  height: 13px;
}

.toggle-arrow {
  width: 13px;
  height: 13px;
}

/* ===== Editor Panel ===== */
.editor-panel {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  overflow: hidden;
}

.editor-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-secondary, #fafafa);
  overflow-x: auto;
}

.editor-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.editor-tab:hover {
  color: var(--text-primary, #374151);
  background: rgba(0, 0, 0, 0.02);
}

.editor-tab.is-selected {
  color: var(--primary-color, #3b82f6);
  border-bottom-color: var(--primary-color, #3b82f6);
  background: white;
}

.editor-tab.is-disabled {
  opacity: 0.35;
}

.tab-emoji {
  font-size: 13px;
}

.tab-dot {
  width: 5px;
  height: 5px;
  background: var(--primary-color, #3b82f6);
  border-radius: 50%;
  flex-shrink: 0;
}

/* ===== Config Form ===== */
.config-form {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.config-header {
  display: flex;
  justify-content: flex-end;
  min-height: 0;
}

.config-header:empty {
  display: none;
}

.reset-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
  padding: 3px 8px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.15s;
}

.reset-btn:hover {
  color: var(--primary-color, #3b82f6);
  border-color: var(--primary-color, #3b82f6);
}

.icon-xs {
  width: 12px;
  height: 12px;
}

/* ===== Form Fields ===== */
.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary, #6b7280);
}

.field-input {
  padding: 6px 10px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-primary, #111827);
  transition: border-color 0.2s;
}

.field-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.field-textarea {
  padding: 6px 10px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-primary, #111827);
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s;
}

.field-textarea:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.field-input::placeholder,
.field-textarea::placeholder {
  color: var(--text-weak, #d1d5db);
}

.field-hint {
  font-size: 11px;
  color: var(--text-weak, #d1d5db);
}
</style>
