import { useUserStore } from './stores/user'

function registerTools() {
  const mc = (navigator as any).modelContext
  const router = (window as any).__vue_router

  const getAuthHeaders = (): Record<string, string> => {
    const raw = localStorage.getItem('bw_user_tokens')
    if (!raw) return {}
    try { return { Authorization: `Bearer ${JSON.parse(raw).access_token}` } }
    catch { return {} }
  }

  const tools = [
    // === Auth ===
    {
      name: 'bw_login',
      description: 'Login with username and password',
      inputSchema: { type: 'object', properties: { username: { type: 'string' }, password: { type: 'string' } }, required: ['username', 'password'] },
      execute: async (p: any) => {
        try { const s = useUserStore(); await s.login(p.username, p.password); return { ok: true, user: s.user } }
        catch (e: any) { return { error: typeof e === 'string' ? e : e?.message || JSON.stringify(e) } }
      }
    },
    {
      name: 'bw_logout',
      description: 'Logout current user',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => { await useUserStore().logout(); return { ok: true } }
    },

    
    {
      name: 'bw_register',
      description: 'Register a new user',
      inputSchema: { type: 'object', properties: { username: { type: 'string' }, password: { type: 'string' }, display_name: { type: 'string' } }, required: ['username', 'password'] },
      execute: async (p: any) => {
        try { const s = useUserStore(); await s.register(p.username, p.password, p.display_name); return { ok: true, user: s.user } }
        catch (e: any) { return { error: typeof e === 'string' ? e : e?.message || JSON.stringify(e) } }
      }
    },

    // === Page State ===
    {
      name: 'bw_get_page_state',
      description: 'Get structured page state: current page type, key elements, data counts',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const s = useUserStore()
        const path = location.pathname
        let pageType = 'unknown'
        let pageData: any = {}

        if (path === '/' || path === '') {
          pageType = 'project_list'
          pageData = {
            projectCards: document.querySelectorAll('.project-card').length,
            hasCreateBtn: !!document.querySelector('.btn-primary'),
            hasCreateDialog: !!document.querySelector('.modal-mask'),
          }
        } else if (path.match(/^\/project\/[^/]+$/)) {
          pageType = 'workspace'
          pageData = {
            projectId: path.split('/')[2],
            projectName: document.querySelector('.app-title')?.textContent?.trim(),
            discussionCards: document.querySelectorAll('.card').length,
            hasBackBtn: !!document.querySelector('.back-btn'),
          }
        } else if (path.match(/\/discussion\//)) {
          pageType = 'discussion'
          pageData = {
            discussionId: path.split('/').pop(),
          }
        }

        return {
          pageType,
          path,
          isAuthenticated: s.isAuthenticated,
          user: s.user ? { id: s.user.id, username: s.user.username, role: s.user.role } : null,
          isAdmin: s.isAdmin,
          loginModalVisible: !!document.querySelector('.login-modal, .modal-mask'),
          ...pageData,
        }
      }
    },

    // === Navigation ===
    {
      name: 'bw_navigate_project',
      description: 'Navigate to a project workspace',
      inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
      execute: async (p: any) => {
        if (router) { router.push(`/project/${p.id}`); }
        else { location.href = `/project/${p.id}`; }
        await new Promise(r => setTimeout(r, 1500))
        return { ok: true, url: location.href }
      }
    },
    {
      name: 'bw_back_to_projects',
      description: 'Navigate back to project list',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        if (router) { router.push('/'); }
        else { location.href = '/'; }
        await new Promise(r => setTimeout(r, 1500))
        return { ok: true, url: location.href }
      }
    },

    // === Projects ===
    {
      name: 'bw_list_projects',
      description: 'List projects via API',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const res = await fetch('/api/projects', { headers: getAuthHeaders() })
        if (!res.ok) return { error: (await res.json()).detail }
        return await res.json()
      }
    },
    {
      name: 'bw_list_project_members',
      description: 'List members of a project',
      inputSchema: { type: 'object', properties: { project_id: { type: 'string' } }, required: ['project_id'] },
      execute: async (p: any) => {
        const res = await fetch(`/api/projects/${p.project_id}/members`, { headers: getAuthHeaders() })
        if (!res.ok) return { error: (await res.json()).detail }
        return await res.json()
      }
    },
    {
      name: 'bw_add_project_member',
      description: 'Add a member to a project',
      inputSchema: { type: 'object', properties: { project_id: { type: 'string' }, username: { type: 'string' }, role: { type: 'string' } }, required: ['project_id', 'username'] },
      execute: async (p: any) => {
        const res = await fetch(`/api/projects/${p.project_id}/members`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({ username: p.username, role: p.role || 'member' })
        })
        if (!res.ok) return { error: (await res.json()).detail }
        return await res.json()
      }
    },

    // === Discussions ===
    {
      name: 'bw_list_discussions',
      description: 'List discussions via API',
      inputSchema: { type: 'object', properties: { all: { type: 'boolean' } } },
      execute: async (p: any) => {
        const url = p?.all ? '/api/discussions?all=true' : '/api/discussions'
        const res = await fetch(url, { headers: getAuthHeaders() })
        const data = await res.json()
        if (!res.ok) return { error: data.detail }
        const items = data.items || data
        return { count: items.length, discussions: items.map((d: any) => ({ id: d.id, topic: d.topic, status: d.status, owner_id: d.owner_id, owner_name: d.owner_name })) }
      }
    },
    {
      name: 'bw_get_discussion',
      description: 'Get discussion by ID',
      inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
      execute: async (p: any) => {
        const res = await fetch(`/api/discussions/${p.id}`, { headers: getAuthHeaders() })
        if (!res.ok) return { error: (await res.json()).detail }
        return await res.json()
      }
    },
    {
      name: 'bw_delete_discussion',
      description: 'Delete a discussion by ID',
      inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
      execute: async (p: any) => {
        const res = await fetch(`/api/discussions/${p.id}`, { method: 'DELETE', headers: getAuthHeaders() })
        if (!res.ok) return { error: (await res.json()).detail }
        return { ok: true }
      }
    },

    // === UI Actions ===
    {
      name: 'bw_open_create_dialog',
      description: 'Open project create dialog (project list page only)',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const btn = document.querySelector('.section-header .btn-primary') as HTMLElement
        if (!btn) return { error: 'Create button not found (not on project list page?)' }
        btn.click()
        await new Promise(r => setTimeout(r, 300))
        return { ok: true, dialogVisible: !!document.querySelector('.modal-mask') }
      }
    },
    {
      name: 'bw_close_dialog',
      description: 'Close any open modal dialog',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const mask = document.querySelector('.modal-mask') as HTMLElement
        if (mask) mask.click()
        await new Promise(r => setTimeout(r, 300))
        return { ok: true }
      }
    },

    // === Hall Tools ===
    {
      name: 'bw_hall_stats',
      description: 'Get hall page stats: total_items, discussions_count, projects_count, active_filter, search_query',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const hall = (window as any).__bwHall
        if (!hall) return { error: 'Not on hall page' }
        const items = hall.filteredItems || []
        return {
          total_items: items.length,
          discussions_count: items.filter((i: any) => i.type === 'discussion').length,
          projects_count: items.filter((i: any) => i.type === 'project').length,
          active_filter: hall.activeTab,
          search_query: hall.searchQuery,
        }
      }
    },
    {
      name: 'bw_hall_items',
      description: 'Get current visible hall card list [{type, id, name, status}]',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const hall = (window as any).__bwHall
        if (!hall) return { error: 'Not on hall page' }
        return (hall.filteredItems || []).map((i: any) => ({
          type: i.type,
          id: i.id,
          name: i.name,
          status: i.extra?.status || '',
          is_public: i.is_public,
          user_role: i.user_role,
        }))
      }
    },
    {
      name: 'bw_create_discussion',
      description: 'Create a new discussion by filling and submitting the dialog',
      inputSchema: { type: 'object', properties: { topic: { type: 'string' }, project_id: { type: 'string' } }, required: ['topic'] },
      execute: async (p: any) => {
        const hall = (window as any).__bwHall
        if (!hall) return { error: 'Not on hall page' }
        hall.newDiscussionTopic.value = p.topic
        hall.newDiscussionProjectId.value = p.project_id || ''
        hall.showNewDiscussion.value = true
        await new Promise(r => setTimeout(r, 100))
        await hall.doCreateDiscussion()
        return { ok: true }
      }
    },
    {
      name: 'bw_create_project',
      description: 'Create a new project by filling and submitting the dialog',
      inputSchema: { type: 'object', properties: { name: { type: 'string' }, description: { type: 'string' } }, required: ['name'] },
      execute: async (p: any) => {
        const hall = (window as any).__bwHall
        if (!hall) return { error: 'Not on hall page' }
        hall.newProjectName.value = p.name
        hall.newProjectDescription.value = p.description || ''
        hall.showNewProject.value = true
        await new Promise(r => setTimeout(r, 100))
        await hall.doCreateProject()
        return { ok: true }
      }
    },
    {
      name: 'bw_open_new_discussion',
      description: 'Open new discussion dialog on hall page',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('新讨论')) as HTMLElement
        if (!btn) return { error: 'Not on hall page or button not found' }
        btn.click()
        await new Promise(r => setTimeout(r, 500))
        return { ok: true, dialogOpen: !!document.querySelector('.dialog-overlay') }
      }
    },
    {
      name: 'bw_open_advanced_options',
      description: 'Open advanced options panel in new discussion dialog, optionally switch to a tab',
      inputSchema: { type: 'object', properties: { tab: { type: 'string', description: 'Tab name: 基础 or 人员' } } },
      execute: async (p: any) => {
        const advBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('高级选项')) as HTMLElement
        if (advBtn) { advBtn.click(); await new Promise(r => setTimeout(r, 300)) }
        if (p?.tab) {
          const tab = Array.from(document.querySelectorAll('.adv-tab')).find(t => t.textContent?.includes(p.tab)) as HTMLElement
          if (tab) { tab.click(); await new Promise(r => setTimeout(r, 300)) }
        }
        return { ok: true }
      }
    },
    {
      name: 'bw_crew_list',
      description: 'Get current crew members in personnel tab',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const items = Array.from(document.querySelectorAll('.crew-item'))
        const active = document.querySelector('.crew-item-active')
        return {
          crew: items.map(i => ({
            name: i.querySelector('.crew-name')?.textContent?.trim() || i.textContent?.trim(),
            active: i === active,
            removable: !!i.querySelector('.crew-remove'),
            locked: !!i.querySelector('.crew-lock')
          })),
          activeAgent: active?.querySelector('.crew-name')?.textContent?.trim() || active?.textContent?.trim() || null
        }
      }
    },
    {
      name: 'bw_crew_remove',
      description: 'Remove a crew member by name (partial match)',
      inputSchema: { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] },
      execute: async (p: any) => {
        const items = Array.from(document.querySelectorAll('.crew-item'))
        const target = items.find(i => i.textContent?.includes(p.name))
        if (!target) return { error: 'Agent not found: ' + p.name }
        const removeBtn = target.querySelector('.crew-remove') as HTMLElement
        if (!removeBtn) return { error: 'Agent is locked: ' + p.name }
        target.click(); await new Promise(r => setTimeout(r, 200))
        removeBtn.click(); await new Promise(r => setTimeout(r, 300))
        const newActive = document.querySelector('.crew-item-active')
        const remaining = Array.from(document.querySelectorAll('.crew-item')).map(i => i.querySelector('.crew-name')?.textContent?.trim() || i.textContent?.trim())
        return { ok: true, removed: p.name, newActive: newActive?.querySelector('.crew-name')?.textContent?.trim() || newActive?.textContent?.trim(), remaining }
      }
    },
    {
      name: 'bw_access_modal_state',
      description: 'Check if access-denied modal is showing and its buttons',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const overlay = document.querySelector('.access-overlay')
        const modal = overlay?.querySelector('.access-modal')
        const btns = modal ? Array.from(modal.querySelectorAll('button')).map(b => b.textContent?.trim()) : []
        return { visible: !!overlay, buttons: btns }
      }
    },
    {
      name: 'bw_request_access',
      description: 'Click access request button in the modal (role: viewer or editor)',
      inputSchema: { type: 'object', properties: { role: { type: 'string' } }, required: ['role'] },
      execute: async (p: any) => {
        const keyword = p.role === 'viewer' ? '查看' : '编辑'
        const btn = Array.from(document.querySelectorAll('.access-modal button')).find(b => b.textContent?.includes(keyword)) as HTMLElement
        if (!btn) return { error: 'No button for ' + keyword }
        const origAlert = window.alert
        let alertMsg = ''
        window.alert = (msg: string) => { alertMsg = msg }
        btn.click()
        await new Promise(r => setTimeout(r, 2000))
        window.alert = origAlert
        return { ok: true, alertMessage: alertMsg }
      }
    },
    {
      name: 'bw_pending_requests',
      description: 'Get pending access requests bar (admin view on project detail)',
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const bar = document.querySelector('.pending-bar')
        if (!bar) return { visible: false, count: 0, requests: [] }
        const items = Array.from(bar.querySelectorAll('.pending-item'))
        return {
          visible: true,
          count: items.length,
          requests: items.map(i => ({
            text: i.textContent?.trim(),
            hasApprove: !!i.querySelector('.btn-primary'),
            hasReject: !!i.querySelector('.btn-danger')
          }))
        }
      }
    },
    {
      name: 'bw_approve_request',
      description: 'Approve or reject a pending access request by index',
      inputSchema: { type: 'object', properties: { index: { type: 'number' }, action: { type: 'string' } }, required: ['index', 'action'] },
      execute: async (p: any) => {
        const items = Array.from(document.querySelectorAll('.pending-item'))
        const item = items[p.index || 0]
        if (!item) return { error: 'No request at index ' + p.index }
        const btn = p.action === 'approve' ? item.querySelector('.btn-primary') as HTMLElement : item.querySelector('.btn-danger') as HTMLElement
        if (!btn) return { error: 'No ' + p.action + ' button' }
        btn.click()
        await new Promise(r => setTimeout(r, 2000))
        return { ok: true, action: p.action, remainingRequests: document.querySelectorAll('.pending-item').length }
      }
    },
    {
      name: 'bw_delete_project',
      description: 'Delete a project (superadmin only)',
      inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
      execute: async (p: any) => {
        const token = JSON.parse(localStorage.getItem('bw_user_tokens') || '{}').access_token
        const res = await fetch('/api/projects/' + p.id, { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } })
        const data = await res.json()
        return { status: res.status, ...data }
      }
    },
  ]

  for (const t of tools) {
    if (mc) mc.registerTool({ name: t.name, description: t.description, inputSchema: t.inputSchema, execute: t.execute })
  }
  const bw: Record<string, any> = {}
  for (const t of tools) { bw[t.name] = t.execute }
  ;(window as any).__bw = bw
  console.log(`[WebMCP] ✅ Registered ${tools.length} tools (+ window.__bw)`)
}

export function initWebMCP() {
  if ((navigator as any).modelContext) { registerTools() }
  else {
    let r = 0
    const iv = setInterval(() => {
      if ((navigator as any).modelContext) { clearInterval(iv); registerTools() }
      else if (++r > 20) { clearInterval(iv); registerTools() }
    }, 500)
  }
}
