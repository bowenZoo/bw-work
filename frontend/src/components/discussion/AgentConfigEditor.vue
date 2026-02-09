<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { ChevronDown, ChevronUp, RotateCcw } from 'lucide-vue-next';
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
  { id: 'lead_planner', name: '主策划', locked: true },
  { id: 'system_designer', name: '系统策划', locked: false },
  { id: 'number_designer', name: '数值策划', locked: false },
  { id: 'player_advocate', name: '玩家代言人', locked: false },
  { id: 'visual_concept', name: '视觉概念', locked: false },
];

// Currently selected agent for editing
const selectedAgentId = ref<string | null>(null);

// Expanded state
const isExpanded = ref(false);

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
    // Add lead_planner (locked)
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

// Select first enabled non-locked agent when expanded
watch(isExpanded, (expanded) => {
  if (expanded && !selectedAgentId.value) {
    selectedAgentId.value = 'system_designer';
  }
});
</script>

<template>
  <div class="agent-config-editor">
    <button class="expand-toggle" @click="isExpanded = !isExpanded">
      <span class="toggle-label">Agent 配置</span>
      <span class="toggle-hint">自定义参与者和提示词</span>
      <component :is="isExpanded ? ChevronUp : ChevronDown" class="toggle-icon" />
    </button>

    <div v-if="isExpanded" class="config-body">
      <!-- Agent list (left side) -->
      <div class="agent-list">
        <div
          v-for="role in AGENT_ROLES"
          :key="role.id"
          class="agent-item"
          :class="{
            'is-selected': selectedAgentId === role.id,
            'is-disabled': !isAgentEnabled(role.id),
            'is-locked': role.locked,
          }"
          @click="selectedAgentId = role.id"
        >
          <label class="agent-checkbox" @click.stop>
            <input
              type="checkbox"
              :checked="isAgentEnabled(role.id)"
              :disabled="role.locked"
              @change="toggleAgent(role.id)"
            />
          </label>
          <span class="agent-name">{{ role.name }}</span>
          <span v-if="role.locked" class="locked-badge">必选</span>
          <span v-if="hasOverrides(role.id)" class="modified-dot" title="已自定义" />
        </div>
      </div>

      <!-- Config editor (right side) -->
      <div v-if="selectedAgentId" class="config-form">
        <div class="config-header">
          <span class="config-title">{{ AGENT_ROLES.find(r => r.id === selectedAgentId)?.name }}</span>
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
            rows="3"
            :value="getAgentConfig(selectedAgentId).goal"
            :placeholder="defaultConfigs[selectedAgentId]?.goal || '角色目标'"
            @input="updateConfigField(selectedAgentId!, 'goal', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>

        <div class="form-field">
          <label class="field-label">背景故事</label>
          <textarea
            class="field-textarea"
            rows="4"
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
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  overflow: hidden;
}

.expand-toggle {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 10px 14px;
  background: var(--bg-secondary, #fafafa);
  border: none;
  cursor: pointer;
  gap: 8px;
  transition: background 0.15s;
}

.expand-toggle:hover {
  background: #f3f4f6;
}

.toggle-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #374151);
}

.toggle-hint {
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
  flex: 1;
  text-align: left;
}

.toggle-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary, #9ca3af);
}

.config-body {
  display: grid;
  grid-template-columns: 160px 1fr;
  border-top: 1px solid var(--border-color, #e5e7eb);
  min-height: 280px;
}

.agent-list {
  border-right: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-secondary, #fafafa);
  padding: 6px 0;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 13px;
  color: var(--text-primary, #374151);
}

.agent-item:hover {
  background: #e5e7eb;
}

.agent-item.is-selected {
  background: white;
  font-weight: 500;
  border-right: 2px solid var(--primary-color, #3b82f6);
}

.agent-item.is-disabled {
  opacity: 0.4;
}

.agent-checkbox input {
  width: 14px;
  height: 14px;
  cursor: pointer;
}

.agent-checkbox input:disabled {
  cursor: not-allowed;
}

.agent-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.locked-badge {
  font-size: 10px;
  padding: 1px 4px;
  background: #e5e7eb;
  color: #6b7280;
  border-radius: 3px;
}

.modified-dot {
  width: 6px;
  height: 6px;
  background: var(--primary-color, #3b82f6);
  border-radius: 50%;
  flex-shrink: 0;
}

.config-form {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  max-height: 360px;
}

.config-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.config-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111827);
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

@media (max-width: 640px) {
  .config-body {
    grid-template-columns: 1fr;
  }

  .agent-list {
    display: flex;
    overflow-x: auto;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #e5e7eb);
    padding: 4px 8px;
    gap: 4px;
  }

  .agent-item {
    white-space: nowrap;
    border-radius: 6px;
    padding: 5px 10px;
  }

  .agent-item.is-selected {
    border-right: none;
    border-bottom: 2px solid var(--primary-color, #3b82f6);
  }
}
</style>
