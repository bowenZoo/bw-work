import type { AgentRole } from '@/types';
import leadAvatar from '@/assets/avatars/lead_planner.svg';
import systemAvatar from '@/assets/avatars/system_designer.svg';
import numberAvatar from '@/assets/avatars/number_designer.svg';
import playerAvatar from '@/assets/avatars/player_advocate.svg';
import operationsAvatar from '@/assets/avatars/operations_analyst.svg';
import visualAvatar from '@/assets/avatars/visual_concept.svg';

const ROLE_DISPLAY_NAMES: Record<AgentRole, string> = {
  lead_planner: '主策划',
  system_designer: '系统策划',
  number_designer: '数值策划',
  player_advocate: '玩家代言人',
  operations_analyst: '运营策划',
  visual_concept: '视觉概念',
  creative_director: '创意总监',
  market_director: '市场总监',
};

const ROLE_AVATARS: Record<AgentRole, string | null> = {
  lead_planner: leadAvatar,
  system_designer: systemAvatar,
  number_designer: numberAvatar,
  player_advocate: playerAvatar,
  operations_analyst: operationsAvatar,
  visual_concept: visualAvatar,
  creative_director: null,
  market_director: null,
};

const ROLE_ALIASES: Record<string, AgentRole> = {
  lead_planner: 'lead_planner',
  'lead planner': 'lead_planner',
  '主策划': 'lead_planner',
  system_designer: 'system_designer',
  'system designer': 'system_designer',
  '系统策划': 'system_designer',
  number_designer: 'number_designer',
  'number designer': 'number_designer',
  '数值策划': 'number_designer',
  player_advocate: 'player_advocate',
  'player advocate': 'player_advocate',
  '玩家代言人': 'player_advocate',
  operations_analyst: 'operations_analyst',
  'operations analyst': 'operations_analyst',
  '运营策划': 'operations_analyst',
  visual_concept: 'visual_concept',
  'visual concept': 'visual_concept',
  '视觉概念': 'visual_concept',
  '视觉概念设计师': 'visual_concept',
  creative_director: 'creative_director',
  'creative director': 'creative_director',
  '创意总监': 'creative_director',
  market_director: 'market_director',
  'market director': 'market_director',
  '市场总监': 'market_director',
  '市场运营': 'market_director',
};

export function normalizeAgentRole(role?: string | null): AgentRole | null {
  if (!role) {
    return null;
  }

  const normalized = role.trim().toLowerCase();
  return ROLE_ALIASES[normalized] ?? ROLE_ALIASES[role] ?? null;
}

export function getAgentDisplayName(role?: string | null): string | null {
  const normalized = normalizeAgentRole(role);
  if (!normalized) return null;
  return ROLE_DISPLAY_NAMES[normalized] ?? null;
}

export function getAgentAvatar(role?: string | null): string | null {
  const normalized = normalizeAgentRole(role);
  if (!normalized) return null;
  return ROLE_AVATARS[normalized] ?? null;
}
