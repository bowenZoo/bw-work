You have two tasks. For each Vue file, preserve the existing <script> section EXACTLY, and rewrite ONLY the <template> and <style scoped> sections to match the design preview HTML files.

## Task 1: ProjectDetailView.vue

**Source design HTML**: Read `~/Desktop/bw-work/project-detail.html`
**Target Vue file**: `frontend/src/views/ProjectDetailView.vue`

Keep lines 1-381 (script) unchanged. Rewrite lines 382+ (template + style).

### Data mapping (HTML hardcoded → Vue variables):
- "大厅" back link → `@click="goBackToHall()"`
- "智能客服系统" breadcrumb → `{{ project?.name }}`
- Project title → `{{ project?.name }}`
- Project description → `{{ project?.description }}`
- Avatar group → iterate `project?.members` if available
- "编辑" button → `v-if="canEdit"`
- Stage sections → `v-for="stage in stages" :key="stage.id"`, use `collapsedStages.has(stage.id)` for collapse
- Stage name → `{{ stage.name }}`
- Stage status → `stage.status` ('locked', 'current', 'completed')
- Documents in stage → `v-for="doc in stage.documents"`, `doc.title`, `doc.updated_at`
- Discussion cards in stage → `v-for="disc in stage.discussions"`, `disc.name`, `disc.status`
- "新建讨论" button → `@click="showNewDiscDialog = stage.id"`
- "新建文档" button → `@click="showNewDoc = stage.id"`
- Output cards → `v-for="output in stage.outputs"`, `output.title`
- Adopt button → `@click="showAdoptDialog = output"`
- Pending requests bar → `v-if="isAdmin && pendingRequests.length"`, iterate `pendingRequests`
- Access denied overlay → `v-if="showAccessModal"`
- Keep all existing modals: new doc dialog, new discussion dialog, adopt dialog, preview output, access modal, pending requests

### Components used:
- No external components needed in template (UserMenu is in parent layout)

## Task 2: DocumentView.vue

**Source design HTML**: Read `~/Desktop/bw-work/doc-editor.html`
**Target Vue file**: `frontend/src/views/DocumentView.vue`

Keep lines 1-92 (script) unchanged. Rewrite lines 93+ (template + style).

### Data mapping:
- Breadcrumb: project name → `{{ doc?.project_name }}` or route param, doc title → `{{ doc?.title }}`
- Editor content → `v-model="content"` (textarea or contenteditable)
- Version history sidebar → `v-for="ver in versions"`, `ver.version`, `ver.updated_at`, `ver.updated_by`
- Save button → `@click="saveDoc"`, `saving` ref
- Revert button → `@click="revertTo(ver.version)"`
- Preview toggle → existing `showPreview` ref

### Script variables available:
Read the first 92 lines of DocumentView.vue to see all available refs and functions.

## Rules:
- Match the HTML design EXACTLY for colors, spacing, shadows, border-radius
- Use scoped CSS, no global styles
- All CSS class names should be descriptive (kebab-case)
- Replace hardcoded data with Vue bindings
- Preserve ALL existing modal/dialog templates from the current Vue files
- Do NOT modify anything in the <script> sections
- Write results back to the same Vue files (overwrite template+style, keep script)

