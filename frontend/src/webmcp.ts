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
      name: 'bw_create_project',
      description: 'Create a project (admin only)',
      inputSchema: { type: 'object', properties: { name: { type: 'string' }, description: { type: 'string' }, is_public: { type: 'boolean' } }, required: ['name'] },
      execute: async (p: any) => {
        const slug = p.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 30) + '-' + Math.random().toString(36).slice(2, 6)
        const res = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({ ...p, slug })
        })
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
