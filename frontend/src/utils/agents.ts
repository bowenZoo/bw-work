import type { AgentRole } from '@/types';

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
  visual_concept: 'visual_concept',
  'visual concept': 'visual_concept',
  '视觉概念': 'visual_concept',
  '视觉概念设计师': 'visual_concept',
};

export function normalizeAgentRole(role?: string | null): AgentRole | null {
  if (!role) {
    return null;
  }

  const normalized = role.trim().toLowerCase();
  return ROLE_ALIASES[normalized] ?? ROLE_ALIASES[role] ?? null;
}
