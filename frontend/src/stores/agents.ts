import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Agent, AgentStatus } from '@/types';
import leadAvatar from '@/assets/avatars/lead_planner.svg';
import systemAvatar from '@/assets/avatars/system_designer.svg';
import numberAvatar from '@/assets/avatars/number_designer.svg';
import playerAvatar from '@/assets/avatars/player_advocate.svg';
import operationsAvatar from '@/assets/avatars/operations_analyst.svg';
import visualAvatar from '@/assets/avatars/visual_concept.svg';

const leadAvatarUrl =
  (import.meta.env.VITE_AVATAR_LEAD_PLANNER as string | undefined) || leadAvatar;
const systemAvatarUrl =
  (import.meta.env.VITE_AVATAR_SYSTEM_DESIGNER as string | undefined) || systemAvatar;
const numberAvatarUrl =
  (import.meta.env.VITE_AVATAR_NUMBER_DESIGNER as string | undefined) || numberAvatar;
const playerAvatarUrl =
  (import.meta.env.VITE_AVATAR_PLAYER_ADVOCATE as string | undefined) || playerAvatar;
const operationsAvatarUrl =
  (import.meta.env.VITE_AVATAR_OPERATIONS_ANALYST as string | undefined) || operationsAvatar;
const visualAvatarUrl =
  (import.meta.env.VITE_AVATAR_VISUAL_CONCEPT as string | undefined) || visualAvatar;

export const useAgentsStore = defineStore('agents', () => {
  // State
  const agents = ref<Agent[]>([
    {
      id: 'lead_planner',
      name: '主策划',
      role: 'lead_planner',
      status: 'idle',
      avatarUrl: leadAvatarUrl,
    },
    {
      id: 'system_designer',
      name: '系统策划',
      role: 'system_designer',
      status: 'idle',
      avatarUrl: systemAvatarUrl,
    },
    {
      id: 'number_designer',
      name: '数值策划',
      role: 'number_designer',
      status: 'idle',
      avatarUrl: numberAvatarUrl,
    },
    {
      id: 'player_advocate',
      name: '玩家代言人',
      role: 'player_advocate',
      status: 'idle',
      avatarUrl: playerAvatarUrl,
    },
    {
      id: 'operations_analyst',
      name: '运营策划',
      role: 'operations_analyst',
      status: 'idle',
      avatarUrl: operationsAvatarUrl,
    },
    {
      id: 'visual_concept',
      name: '视觉概念',
      role: 'visual_concept',
      status: 'idle',
      avatarUrl: visualAvatarUrl,
    },
  ]);

  // Getters
  const speakingAgent = computed(() =>
    agents.value.find(agent => agent.status === 'speaking')
  );

  const thinkingAgents = computed(() =>
    agents.value.filter(agent => agent.status === 'thinking')
  );

  const writingAgent = computed(() =>
    agents.value.find(agent => agent.status === 'writing')
  );

  const getAgentById = computed(() => (id: string) =>
    agents.value.find(agent => agent.id === id)
  );

  const getAgentByRole = computed(() => (role: string) =>
    agents.value.find(agent => agent.role === role)
  );

  // Status content (e.g. "正在搜索网页..." shown alongside "思考中")
  const statusContents = ref<Record<string, string>>({});

  // When each agent entered their current active status (ISO timestamp from backend)
  const statusStartedAt = ref<Record<string, string>>({});

  // Actions
  function setAgentStatus(agentId: string, status: AgentStatus, content?: string, startedAt?: string) {
    const agent = agents.value.find(a => a.id === agentId);
    if (agent) {
      agent.status = status;
      if (content) {
        statusContents.value[agentId] = content;
      } else if (status !== 'thinking') {
        delete statusContents.value[agentId];
      }
      const isActive = status === 'thinking' || status === 'speaking' || status === 'writing';
      if (isActive && startedAt) {
        statusStartedAt.value[agentId] = startedAt;
      } else if (!isActive) {
        delete statusStartedAt.value[agentId];
      }
    }
  }

  function setAgentStatusByRole(role: string, status: AgentStatus, content?: string) {
    const agent = agents.value.find(a => a.role === role);
    if (agent) {
      agent.status = status;
      if (content) {
        statusContents.value[agent.id] = content;
      } else if (status !== 'thinking') {
        delete statusContents.value[agent.id];
      }
    }
  }

  function getStatusContent(agentId: string): string | undefined {
    return statusContents.value[agentId];
  }

  function resetAllAgentsStatus() {
    agents.value.forEach(agent => {
      agent.status = 'idle';
    });
    statusContents.value = {};
    statusStartedAt.value = {};
  }

  /**
   * Set which agents are active for the current discussion.
   * Agents not in the list get filtered out of display.
   */
  const activeAgentIds = ref<string[] | null>(null);

  const activeAgents = computed(() => {
    if (!activeAgentIds.value) return agents.value;
    return agents.value.filter(a => activeAgentIds.value!.includes(a.id));
  });

  function setDiscussionAgents(agentIds: string[]) {
    activeAgentIds.value = agentIds;
  }

  function clearDiscussionAgents() {
    activeAgentIds.value = null;
  }

  /**
   * Bulk set agent statuses (from sync message).
   */
  function setDiscussionAgentStatuses(
    statuses: Record<string, AgentStatus>,
    startedAt?: Record<string, string>,
  ) {
    resetAllAgentsStatus();
    for (const [agentId, status] of Object.entries(statuses)) {
      setAgentStatus(agentId, status, undefined, startedAt?.[agentId]);
    }
  }

  return {
    // State
    agents,
    activeAgentIds,
    statusContents,
    statusStartedAt,
    // Getters
    speakingAgent,
    thinkingAgents,
    writingAgent,
    getAgentById,
    getAgentByRole,
    activeAgents,
    // Actions
    setAgentStatus,
    setAgentStatusByRole,
    getStatusContent,
    resetAllAgentsStatus,
    setDiscussionAgents,
    clearDiscussionAgents,
    setDiscussionAgentStatuses,
  };
});
