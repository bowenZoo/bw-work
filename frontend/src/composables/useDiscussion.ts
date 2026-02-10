/**
 * Per-discussion composable — the unified way to interact with a single discussion.
 *
 * Merges the event handling that was previously split between useGlobalDiscussion
 * and the old useDiscussion. Connects to /ws/{discussionId} for real-time updates.
 */
import { ref, computed, watch, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useDiscussionStore, useAgentsStore } from '@/stores';
import { useWebSocket } from './useWebSocket';
import * as discussionApi from '@/api/discussion';
import { getInterventionStatus } from '@/api/intervention';
import type {
  Discussion,
  Message,
  ServerMessage,
  AgentStatus,
  Agenda,
  AgendaItem,
  RoundSummary,
  DocUpdateEvent,
  DocPlan,
  DocPlanWsEvent,
  SectionFocusWsEvent,
  SectionUpdateWsEvent,
  DocRestructureWsEvent,
  SectionReopenedWsEvent,
  LeadPlannerDigestEventData,
  InterventionAssessmentEventData,
  HolisticReviewEventData,
} from '@/types';
import { normalizeAgentRole } from '@/utils/agents';
import api from '@/api';

export function useDiscussion() {
  const router = useRouter();
  const discussionStore = useDiscussionStore();
  const agentsStore = useAgentsStore();

  // Internal state
  const isCreating = ref(false);
  const isStarting = ref(false);

  // Pause/resume state
  const isPaused = ref(false);
  const autoPauseMessage = ref('');

  // Agenda state
  const agenda = ref<Agenda | null>(null);

  // Round summaries
  const roundSummaries = ref<RoundSummary[]>([]);

  // Doc state
  const latestDocUpdate = ref<DocUpdateEvent | null>(null);
  const docPlan = ref<DocPlan | null>(null);
  const docContents = ref<Map<string, string>>(new Map());
  const currentSectionId = ref<string | null>(null);

  // Lead planner digest events
  const leadPlannerDigests = ref<LeadPlannerDigestEventData[]>([]);

  // Intervention assessment events
  const interventionAssessments = ref<InterventionAssessmentEventData[]>([]);

  // Holistic review events
  const holisticReviews = ref<HolisticReviewEventData[]>([]);

  // Current discussion ID
  const discussionId = computed(() => discussionStore.discussionId);

  // WebSocket connection
  const {
    connectionStatus,
    lastMessage,
    connect,
    disconnect,
  } = useWebSocket(discussionId);

  /**
   * Create a new discussion with the given topic
   */
  async function createDiscussion(topic: string): Promise<string | null> {
    if (isCreating.value) return null;

    isCreating.value = true;
    discussionStore.setLoading(true);
    discussionStore.setError(null);

    try {
      // Read attachment from sessionStorage
      let attachment: { filename: string; content: string } | undefined;
      const storedAttachment = sessionStorage.getItem('discussion_attachment');
      if (storedAttachment) {
        try {
          attachment = JSON.parse(storedAttachment);
          sessionStorage.removeItem('discussion_attachment');
        } catch {
          // Ignore invalid JSON
        }
      }

      const response = await discussionApi.createDiscussion({ topic, attachment });

      const discussion: Discussion = {
        id: response.id,
        topic: response.topic,
        messages: [],
        status: response.status,
      };

      discussionStore.setDiscussion(discussion);

      // Navigate to discussion page
      router.push({
        name: 'discussion-by-id',
        params: { id: response.id },
      });

      return response.id;
    } catch (error) {
      console.error('Failed to create discussion:', error);
      discussionStore.setError(
        error instanceof Error ? error.message : 'Failed to create discussion'
      );
      return null;
    } finally {
      isCreating.value = false;
      discussionStore.setLoading(false);
    }
  }

  /**
   * Start the current discussion
   */
  async function startDiscussion(): Promise<boolean> {
    if (!discussionId.value || isStarting.value) return false;

    isStarting.value = true;
    discussionStore.setLoading(true);
    isPaused.value = false;

    try {
      await discussionApi.startDiscussion(discussionId.value);
      discussionStore.startDiscussion();

      // Connect WebSocket to receive real-time updates
      connect();

      return true;
    } catch (error) {
      console.error('Failed to start discussion:', error);
      discussionStore.setError(
        error instanceof Error ? error.message : 'Failed to start discussion'
      );
      return false;
    } finally {
      isStarting.value = false;
      discussionStore.setLoading(false);
    }
  }

  /**
   * Load an existing discussion by ID
   */
  async function loadDiscussion(id: string): Promise<boolean> {
    discussionStore.setLoading(true);
    discussionStore.setError(null);

    // Reset per-discussion state
    isPaused.value = false;
    autoPauseMessage.value = '';
    roundSummaries.value = [];
    latestDocUpdate.value = null;
    docPlan.value = null;
    docContents.value = new Map();
    currentSectionId.value = null;
    agenda.value = null;
    leadPlannerDigests.value = [];
    interventionAssessments.value = [];
    holisticReviews.value = [];

    try {
      const [statusResponse, messagesResponse, interventionStatus, summariesResponse] = await Promise.all([
        discussionApi.getDiscussionStatus(id),
        discussionApi.getDiscussionMessages(id).catch(() => null),
        getInterventionStatus(id).catch(() => null),
        discussionApi.getRoundSummaries(id).catch(() => null),
      ]);

      const messages: Message[] = (messagesResponse?.messages ?? []).map((msg) => {
        const normalizedRole =
          normalizeAgentRole(msg.agent_id) ?? normalizeAgentRole(msg.agent_role);
        return {
          id: msg.id,
          agentId: normalizedRole ?? msg.agent_id,
          agentRole: normalizedRole ?? msg.agent_role,
          content: msg.content,
          timestamp: msg.timestamp,
        };
      });

      const topic = messagesResponse?.discussion.topic ?? statusResponse.topic;

      const discussion: Discussion = {
        id: statusResponse.id,
        topic,
        messages,
        status: statusResponse.status,
        attachment: statusResponse.attachment ?? undefined,
      };

      discussionStore.setDiscussion(discussion);
      isPaused.value = Boolean(interventionStatus?.is_paused);

      // Load round summaries
      if (summariesResponse?.summaries) {
        roundSummaries.value = summariesResponse.summaries;
      }

      // Connect WebSocket if discussion is in progress
      if (discussion.status === 'running') {
        connect();
      }

      return true;
    } catch (error) {
      console.error('Failed to load discussion:', error);
      discussionStore.setError(
        error instanceof Error ? error.message : 'Failed to load discussion'
      );
      return false;
    } finally {
      discussionStore.setLoading(false);
    }
  }

  // Normalize message format
  function normalizeMessage(msg: any): Message {
    return {
      id: msg.id,
      agentId: msg.agent_id || msg.agentId,
      agentRole: msg.agent_role || msg.agentRole,
      content: msg.content,
      timestamp: msg.timestamp,
      sequence: msg.sequence,
    };
  }

  /**
   * Handle incoming WebSocket message — unified handler for all event types
   */
  function handleMessage(message: any) {
    switch (message.type) {
      case 'sync':
        // Initial sync when connecting to per-discussion WebSocket
        if (message.data.messages) {
          const normalized = message.data.messages.map(normalizeMessage);
          // Replace store messages with synced ones
          if (discussionStore.currentDiscussion) {
            discussionStore.currentDiscussion.messages = normalized;
          }
        }
        if (message.data.is_paused) {
          isPaused.value = true;
          autoPauseMessage.value = '讨论已暂停';
        } else {
          isPaused.value = false;
          autoPauseMessage.value = '';
        }
        if (message.data.round_summaries) {
          roundSummaries.value = message.data.round_summaries;
        }
        if (message.data.agent_statuses) {
          agentsStore.resetAllAgentsStatus();
          for (const [agentId, status] of Object.entries(message.data.agent_statuses)) {
            agentsStore.setAgentStatus(agentId, status as AgentStatus);
          }
        }
        if (message.data.doc_plan) {
          docPlan.value = message.data.doc_plan;
          currentSectionId.value = message.data.doc_plan.current_section_id;
        }
        if (message.data.doc_contents) {
          const newMap = new Map<string, string>();
          for (const [filename, content] of Object.entries(message.data.doc_contents)) {
            newMap.set(filename, content as string);
          }
          docContents.value = newMap;
        }
        break;

      case 'message':
        if (message.data?.agent_id && message.data?.content) {
          const normalizedRole =
            normalizeAgentRole(message.data.agent_id) ??
            normalizeAgentRole(message.data.agent_role);
          const agentRole = normalizedRole ?? message.data.agent_role ?? message.data.agent_id;
          const newMessage: Message = {
            id: `${message.data.discussion_id || discussionId.value}-${Date.now()}`,
            agentId: agentRole,
            agentRole,
            content: message.data.content,
            timestamp: message.data.timestamp,
            sequence: message.data.sequence,
          };
          discussionStore.addMessage(newMessage);
        }
        break;

      case 'status':
        // Discussion-level events
        if (message.data?.agent_role === 'discussion' || message.data?.agent_id === 'discussion') {
          const content = message.data.content || '';
          if (content === 'discussion_completed') {
            isPaused.value = false;
            discussionStore.endDiscussion();
          } else if (content === 'discussion_failed') {
            isPaused.value = false;
            discussionStore.setStatus('failed');
          } else if (content.startsWith('discussion_auto_paused')) {
            isPaused.value = true;
            const colonIdx = content.indexOf(':');
            autoPauseMessage.value = colonIdx >= 0 ? content.substring(colonIdx + 1) : '讨论已自动暂停';
          } else if (content === 'discussion_paused') {
            isPaused.value = true;
            autoPauseMessage.value = '讨论已暂停';
          } else if (content === 'discussion_resumed') {
            isPaused.value = false;
            autoPauseMessage.value = '';
            discussionStore.setStatus('running');
          }
          break;
        }
        // Agent status update
        if (message.data?.agent_id && message.data?.status) {
          agentsStore.setAgentStatus(
            message.data.agent_id,
            message.data.status as AgentStatus
          );
        } else if (message.data?.agent_role && message.data?.status) {
          const normalizedRole =
            normalizeAgentRole(message.data.agent_role) ??
            normalizeAgentRole(message.data.agent_id);
          if (normalizedRole) {
            agentsStore.setAgentStatusByRole(normalizedRole, message.data.status as AgentStatus);
          }
        }
        break;

      case 'agenda':
        handleAgendaEvent(message);
        break;

      case 'round_summary': {
        const summary: RoundSummary = {
          round: message.data.round,
          content: message.data.content,
          key_points: message.data.key_points || [],
          open_questions: message.data.open_questions || [],
          generated_at: message.data.generated_at,
        };
        const existingIdx = roundSummaries.value.findIndex(s => s.round === summary.round);
        if (existingIdx >= 0) {
          roundSummaries.value[existingIdx] = summary;
        } else {
          roundSummaries.value.push(summary);
        }
        break;
      }

      case 'doc_update':
        latestDocUpdate.value = message.data;
        break;

      case 'doc_plan': {
        const evt = message as DocPlanWsEvent;
        docPlan.value = evt.data.doc_plan;
        currentSectionId.value = evt.data.doc_plan.current_section_id;
        break;
      }

      case 'section_focus': {
        const evt = message as SectionFocusWsEvent;
        currentSectionId.value = evt.data.section_id;
        if (docPlan.value) {
          for (const file of docPlan.value.files) {
            for (const section of file.sections) {
              if (section.id === evt.data.section_id) {
                section.status = 'in_progress';
              }
            }
          }
          docPlan.value = { ...docPlan.value, current_section_id: evt.data.section_id };
        }
        break;
      }

      case 'section_update': {
        const evt = message as SectionUpdateWsEvent;
        const newMap = new Map(docContents.value);
        newMap.set(evt.data.filename, evt.data.content);
        docContents.value = newMap;
        break;
      }

      case 'doc_restructure': {
        const evt = message as DocRestructureWsEvent;
        if (evt.data.updated_doc_plan) {
          docPlan.value = evt.data.updated_doc_plan as DocPlan;
          currentSectionId.value = evt.data.updated_doc_plan.current_section_id ?? null;
        }
        break;
      }

      case 'section_reopened': {
        const evt = message as SectionReopenedWsEvent;
        if (docPlan.value) {
          for (const file of docPlan.value.files) {
            for (const section of file.sections) {
              if (section.id === evt.data.section_id) {
                section.status = 'pending';
                section.reopened_reason = evt.data.reason;
                section.revision_count = (section.revision_count || 0) + 1;
              }
            }
          }
          docPlan.value = { ...docPlan.value };
        }
        break;
      }

      case 'lead_planner_digest': {
        leadPlannerDigests.value = [...leadPlannerDigests.value, message.data];
        break;
      }

      case 'intervention_assessment': {
        interventionAssessments.value = [...interventionAssessments.value, message.data];
        // If REOPEN, highlight affected sections
        if (message.data.impact_level === 'REOPEN' && docPlan.value) {
          for (const file of docPlan.value.files) {
            for (const section of file.sections) {
              if (message.data.affected_sections?.includes(section.id)) {
                section.status = 'pending';
              }
            }
          }
          docPlan.value = { ...docPlan.value };
        }
        break;
      }

      case 'holistic_review': {
        holisticReviews.value = [...holisticReviews.value, message.data];
        break;
      }

      case 'error':
        console.error('Discussion error:', message.data?.content);
        discussionStore.setError(message.data?.content ?? 'Unknown error');
        break;

      case 'pong':
        break;

      default:
        console.debug('Unknown message type:', message.type);
    }
  }

  // Agenda event handling
  function handleAgendaEvent(message: any) {
    const { event_type, item_id, title, summary, current_index, agenda: newAgenda } = message.data;

    switch (event_type) {
      case 'agenda_init':
        if (newAgenda) agenda.value = newAgenda;
        break;
      case 'item_start':
        if (agenda.value && item_id) {
          updateAgendaItem(item_id, { status: 'in_progress' });
          if (current_index !== undefined) agenda.value.current_index = current_index;
        }
        break;
      case 'item_complete':
        if (agenda.value && item_id) {
          updateAgendaItem(item_id, { status: 'completed', summary: summary || null });
          if (current_index !== undefined) agenda.value.current_index = current_index;
        }
        break;
      case 'item_skip':
        if (agenda.value && item_id) {
          updateAgendaItem(item_id, { status: 'skipped' });
          if (current_index !== undefined) agenda.value.current_index = current_index;
        }
        break;
      case 'item_add':
        if (agenda.value && item_id && title) {
          const exists = agenda.value.items.some(item => item.id === item_id);
          if (!exists) {
            agenda.value.items.push({
              id: item_id,
              title,
              description: null,
              status: 'pending',
              summary: null,
              summary_details: null,
              started_at: null,
              completed_at: null,
              related_sections: [],
              priority: 0,
              source: 'initial',
            });
          }
        }
        break;
      case 'mapping_update':
        if (agenda.value && message.data.mappings) {
          const mappings = message.data.mappings as Record<string, string[]>;
          for (const item of agenda.value.items) {
            if (mappings[item.id]) {
              item.related_sections = mappings[item.id];
            }
          }
          agenda.value = { ...agenda.value };
        }
        break;
    }
  }

  function updateAgendaItem(itemId: string, updates: Partial<AgendaItem>) {
    if (!agenda.value) return;
    const idx = agenda.value.items.findIndex(item => item.id === itemId);
    if (idx !== -1) {
      agenda.value.items[idx] = { ...agenda.value.items[idx], ...updates };
    }
  }

  // Agenda API methods
  async function fetchAgenda(): Promise<Agenda | null> {
    const id = discussionId.value;
    if (!id) return null;
    try {
      const response = await api.get<Agenda>(`/api/discussions/${id}/agenda`);
      agenda.value = response.data;
      return response.data;
    } catch {
      return null;
    }
  }

  async function addAgendaItem(title: string, description?: string): Promise<AgendaItem | null> {
    const id = discussionId.value;
    if (!id) return null;
    try {
      const response = await api.post<{ item: AgendaItem; message: string }>(
        `/api/discussions/${id}/agenda/items`,
        { title, description }
      );
      if (agenda.value) {
        agenda.value.items.push(response.data.item);
      }
      return response.data.item;
    } catch {
      return null;
    }
  }

  async function skipAgendaItem(itemId: string): Promise<boolean> {
    const id = discussionId.value;
    if (!id) return false;
    try {
      await api.post(`/api/discussions/${id}/agenda/items/${itemId}/skip`);
      updateAgendaItem(itemId, { status: 'skipped' });
      return true;
    } catch {
      return false;
    }
  }

  async function getAgendaItemSummary(itemId: string): Promise<{ summary: string | null; details: any } | null> {
    const id = discussionId.value;
    if (!id) return null;
    try {
      const response = await api.get(`/api/discussions/${id}/agenda/items/${itemId}/summary`);
      return {
        summary: response.data.summary,
        details: response.data.summary_details,
      };
    } catch {
      return null;
    }
  }

  // Focus section
  async function focusSection(sectionId: string): Promise<void> {
    const id = discussionId.value;
    if (!id) return;
    try {
      await api.post(`/api/discussions/${id}/focus-section`, { section_id: sectionId });
    } catch (error) {
      console.error('Failed to focus section:', error);
    }
  }

  // Resume discussion
  async function resumeDiscussion(): Promise<void> {
    const id = discussionId.value;
    if (!id) return;
    await api.post(`/api/discussions/${id}/resume`);
    isPaused.value = false;
    autoPauseMessage.value = '';
  }

  // Pause discussion
  async function pauseDiscussion(): Promise<void> {
    const id = discussionId.value;
    if (!id) return;
    const { pauseDiscussion: pauseApi } = await import('@/api/intervention');
    await pauseApi(id);
  }

  /**
   * End the current discussion
   */
  function endDiscussion() {
    disconnect();
    agentsStore.resetAllAgentsStatus();
    discussionStore.endDiscussion();
  }

  /**
   * Clear and reset everything
   */
  function reset() {
    disconnect();
    agentsStore.resetAllAgentsStatus();
    discussionStore.clearDiscussion();
    isPaused.value = false;
    autoPauseMessage.value = '';
    roundSummaries.value = [];
    latestDocUpdate.value = null;
    docPlan.value = null;
    docContents.value = new Map();
    currentSectionId.value = null;
    agenda.value = null;
    leadPlannerDigests.value = [];
    interventionAssessments.value = [];
    holisticReviews.value = [];
  }

  function setPaused(value: boolean) {
    isPaused.value = value;
  }

  // Watch WebSocket messages
  watch(lastMessage, (message) => {
    if (message) {
      handleMessage(message);
    }
  });

  // Cleanup on unmount
  onUnmounted(() => {
    // Don't full reset — just disconnect WS. The store persists across components.
    disconnect();
  });

  return {
    // State
    discussionId,
    connectionStatus,
    lastMessage,
    isCreating,
    isStarting,
    // Discussion store proxies
    discussion: computed(() => discussionStore.currentDiscussion),
    messages: computed(() => discussionStore.messages),
    topic: computed(() => discussionStore.topic),
    status: computed(() => discussionStore.status),
    isLoading: computed(() => discussionStore.isLoading),
    error: computed(() => discussionStore.error),
    isInProgress: computed(() => discussionStore.isInProgress),
    isCompleted: computed(() => discussionStore.isCompleted),
    setError: discussionStore.setError,

    // Pause/resume
    isPaused: computed(() => isPaused.value),
    autoPauseMessage: computed(() => autoPauseMessage.value),

    // Agenda
    agenda,

    // Round summaries
    roundSummaries,
    latestDocUpdate,

    // Doc state
    docPlan,
    docContents,
    currentSectionId,

    // Dynamic discussion events
    leadPlannerDigests,
    interventionAssessments,
    holisticReviews,

    // Actions
    createDiscussion,
    startDiscussion,
    loadDiscussion,
    handleMessage,
    endDiscussion,
    reset,
    setPaused,
    connect,
    disconnect,
    resumeDiscussion,
    pauseDiscussion,
    focusSection,

    // Agenda actions
    fetchAgenda,
    addAgendaItem,
    skipAgendaItem,
    getAgendaItemSummary,
    updateAgendaItem,
  };
}
