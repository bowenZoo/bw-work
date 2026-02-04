import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Agent, AgentStatus } from '@/types';

export const useAgentsStore = defineStore('agents', () => {
  // State
  const agents = ref<Agent[]>([
    {
      id: 'system_designer',
      name: '系统策划',
      role: 'system_designer',
      status: 'idle',
    },
    {
      id: 'number_designer',
      name: '数值策划',
      role: 'number_designer',
      status: 'idle',
    },
    {
      id: 'player_advocate',
      name: '玩家代言人',
      role: 'player_advocate',
      status: 'idle',
    },
  ]);

  // Getters
  const speakingAgent = computed(() =>
    agents.value.find(agent => agent.status === 'speaking')
  );

  const thinkingAgents = computed(() =>
    agents.value.filter(agent => agent.status === 'thinking')
  );

  const getAgentById = computed(() => (id: string) =>
    agents.value.find(agent => agent.id === id)
  );

  const getAgentByRole = computed(() => (role: string) =>
    agents.value.find(agent => agent.role === role)
  );

  // Actions
  function setAgentStatus(agentId: string, status: AgentStatus) {
    const agent = agents.value.find(a => a.id === agentId);
    if (agent) {
      agent.status = status;
    }
  }

  function setAgentStatusByRole(role: string, status: AgentStatus) {
    const agent = agents.value.find(a => a.role === role);
    if (agent) {
      agent.status = status;
    }
  }

  function resetAllAgentsStatus() {
    agents.value.forEach(agent => {
      agent.status = 'idle';
    });
  }

  return {
    // State
    agents,
    // Getters
    speakingAgent,
    thinkingAgents,
    getAgentById,
    getAgentByRole,
    // Actions
    setAgentStatus,
    setAgentStatusByRole,
    resetAllAgentsStatus,
  };
});
