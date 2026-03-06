# Task: Generate HallView.vue template + style from Pencil design

## What to do
1. Use Pencil MCP tool `get_screenshot` to capture frame `UvniA` (大厅首页/Hall Homepage)
2. Use Pencil MCP tool `snapshot_layout` on frame `UvniA` to get exact layout specs (colors, spacing, fonts, shadows, border-radius)
3. Generate a complete Vue 3 SFC file with ONLY `<template>` and `<style scoped>` sections (NO `<script>` section)
4. Save the output to `frontend/src/views/HallView.template.vue`

## Design-to-Code mapping rules

The template must use these existing variables/functions from the script (already implemented):
- `searchQuery` (v-model for search input)
- `activeTab` (current tab key)
- `tabs` (array of {key, label})
- `filteredItems` (computed array of HallItem)
- `loading` (boolean)
- `userStore.isAuthenticated` (boolean)
- `showLoginModal`, `showNewDiscussion`, `showNewProject`, `showFabMenu` (boolean refs)
- `showAdvancedModal`, `showAgentPicker`, `showAccessModal` (boolean refs)
- `onCardClick(item)` — click handler for cards
- `doCreateDiscussion()` — create discussion
- `doCreateProject()` — create project
- `onLoginSuccess()` — login callback
- `resetDiscussionForm()` — reset form
- `formatTime(dt: string)` — returns relative time string
- `itemStatus(item)` — returns status string like 'running', 'completed', etc.

### HallItem data structure:
```typescript
interface HallItem {
  type: 'discussion' | 'project'
  id: string
  name: string
  description: string
  updated_at: string
  extra: Record<string, any>  // contains: status, current_stage, stage_progress, participants_count, message_count, owner_name, project_name
}
```

### Card rendering rules:
- **Project cards**: Show folder icon + name + current_stage + progress bar (from extra.stage_progress "3/9" format) + status pill
- **Discussion cards**: Show chat icon + name + project tag (extra.project_name) + live status text + time
- Card accent color: purple (#7C3AED) for projects, green (#3D8A5A) for active discussions, gray for completed
- Use SVG icons, NOT emoji characters

## Modals to include in template
Keep these modal templates (they use existing script variables):
1. LoginModal component: `<LoginModal v-if="showLoginModal" @close="showLoginModal = false" @login-success="onLoginSuccess" />`
2. Access request modal (showAccessModal)
3. New discussion modal (showNewDiscussion) with form fields: topic, project select, goal textarea, advanced options button
4. New project modal (showNewProject) with form fields: name, description, isPublic checkbox
5. Advanced options modal (showAdvancedModal) with tabs: 基础 (style, template, password, attachment, focus areas) and 人员 (crew list)
6. Agent picker modal (showAgentPicker)

## Important form variables for modals:
- newDiscussionTopic, newDiscussionProjectId, discussionGoal
- newProjectName, newProjectDescription, newProjectIsPublic
- advancedTab ('base' | 'crew')
- selectedStyle, selectedTemplate, discussionPassword
- attachmentFile, focusAreas, selectedAgents
- enabledAgentRoles, availableAgentRoles, crewSelectedId, crewSelectedRole, crewSelectedConfig
- agentConfigs, agentColors (array of color strings)
- projectItems (for project select dropdown)
- discussionStylesFull, discussionTemplates

## Components to import (already in script):
- UserMenu
- LoginModal
- AgentConfigEditor

## Style requirements:
- Match Pencil design EXACTLY — use snapshot_layout for precise values
- Background: warm cream (#FFFBF5)
- Cards: white, 16px border-radius, soft shadow, 4px top accent bar
- Purple primary: #7C3AED
- Green accent: #3D8A5A
- Grid: responsive, 4 columns on desktop
- NO emoji anywhere in the UI

## Output
Save to: `frontend/src/views/HallView.template.vue`
This file should contain ONLY `<template>...</template>` and `<style scoped>...</style>` — NO script tag.
