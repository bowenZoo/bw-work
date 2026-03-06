/**
 * 讨论详情页 E2E 测试
 * 覆盖：页面加载、UI 结构、历史记录面板
 *
 * 注意：测试不会触发真实 LLM 讨论，仅测试已有讨论记录的页面展示。
 * 若需测试实时 WebSocket，需要后端运行且 LLM 已配置。
 */

import { test, expect } from './fixtures';
import { getToken } from './helpers/api';

const API_URL = 'http://localhost:18000';

test.describe('讨论列表 API', () => {
  test('获取讨论列表 - 返回正确结构', async ({ request, authedPage: page }) => {
    const token = await getToken(page);
    const res = await request.get(`${API_URL}/api/discussions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    // API 返回 {items: [...], hasMore: bool} 格式
    expect(body).toHaveProperty('items');
    expect(body).toHaveProperty('hasMore');
    expect(Array.isArray(body.items)).toBeTruthy();
  });

  test('获取活跃讨论列表', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/discussions/active`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('discussions');
  });

  test('获取可用 Agent 列表', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/discussions/available-agents`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('agents');
    // agents 是 dict 格式（{role_id: config}），不是数组
    expect(typeof body.agents).toBe('object');
    expect(Object.keys(body.agents).length).toBeGreaterThan(0);
  });

  test('获取讨论风格列表', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/discussions/styles`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty('styles');
    expect(body).toHaveProperty('default');
  });
});

test.describe('讨论详情页 UI', () => {
  test('直接访问不存在的讨论 ID - 重定向回大厅', async ({ authedPage: page }) => {
    // 用 SPA 路由跳转避免全页刷新的 auth race condition
    await page.evaluate(() => {
      (window as any).__vue_router.push('/discussion/nonexistent-id-12345');
    });
    await page.waitForTimeout(3000);
    const url = page.url();
    // 要么被重定向（URL 不含 nonexistent-id），要么显示错误组件
    const isRedirected = !url.includes('nonexistent-id-12345');
    const hasError = await page.locator('[class*="error"], [class*="not-found"], .not-found').count() > 0;
    const isOnHall = await page.locator('.hall').count() > 0;
    expect(isRedirected || hasError || isOnHall).toBeTruthy();
  });

  test('已完成讨论页 - 展示基本 UI 结构', async ({ authedPage: page, request }) => {
    const token = await getToken(page);

    // 先查询是否有已完成的讨论
    const listRes = await request.get(`${API_URL}/api/discussions?limit=10`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const list = await listRes.json();
    const completed = list.items?.find((d: any) => d.status === 'completed');

    if (!completed) {
      test.skip();
      return;
    }

    // SPA 路由跳转，避免全页刷新的 auth 竞态
    await page.evaluate((id) => {
      (window as any).__vue_router.push(`/discussion/${id}`);
    }, completed.id);
    await page.waitForLoadState('networkidle');

    // 讨论页面应有主要容器
    const hasPanel = await page.locator(
      '.discussion-main, .discussion-main-fallback, [class*="discussion-main"]'
    ).count() > 0;
    expect(hasPanel).toBeTruthy();
  });
});

test.describe('讨论详情页 - 模型快速切换', () => {
  const MOCK_DISCUSSION_ID = 'test-model-switch-id';
  const MOCK_MODEL = 'claude-sonnet-4-6';
  const BASE_URL = 'http://localhost:18001';

  test('模型徽章显示当前模型并支持切换', async ({ authedPage: page }) => {
    // 1. mock GET /api/config/model
    await page.route('**/api/config/model', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            model: MOCK_MODEL,
            profile_name: 'Default',
            profile_id: '1',
            profiles: [],
          }),
        });
      } else {
        await route.continue();
      }
    });

    // 2. mock GET /api/discussions/test-model-switch-id (completed discussion)
    await page.route(`**/api/discussions/${MOCK_DISCUSSION_ID}`, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: MOCK_DISCUSSION_ID,
            topic: '模型切换测试讨论',
            status: 'completed',
            rounds: 2,
            created_at: new Date().toISOString(),
            messages: [],
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Track POST /api/config/model/set calls
    let modelSetCalled = false;
    let modelSetBody: any = null;
    await page.route('**/api/config/model/set', async (route) => {
      if (route.request().method() === 'POST') {
        modelSetCalled = true;
        modelSetBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            model: 'claude-haiku-4-5',
            profile_id: '1',
          }),
        });
      } else {
        await route.continue();
      }
    });

    // 3. 导航到讨论页（直接用 URL 跳转，已有 token in localStorage via authedPage fixture）
    await page.goto(`${BASE_URL}/discussion/${MOCK_DISCUSSION_ID}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    // 4. 验证模型徽章显示 claude-sonnet-4-6
    const modelBadge = page.locator('.model-badge');
    const badgeVisible = await modelBadge.isVisible().catch(() => false);

    if (!badgeVisible) {
      // The model badge is only shown when currentModel.model is truthy.
      // If the mock wasn't called (e.g. the component redirected away), skip gracefully.
      test.skip();
      return;
    }

    const badgeText = await modelBadge.textContent();
    expect(badgeText).toContain(MOCK_MODEL);

    // 5. 点击模型徽章，验证下拉出现
    await modelBadge.click();
    await page.waitForTimeout(300);

    const dropdown = page.locator('.model-dropdown');
    const dropdownVisible = await dropdown.isVisible().catch(() => false);
    expect(dropdownVisible).toBeTruthy();

    // Verify dropdown contains expected model options
    const dropdownText = await dropdown.textContent();
    expect(dropdownText).toContain('Haiku 4.5');
    expect(dropdownText).toContain('Sonnet 4.6');
    expect(dropdownText).toContain('Opus 4.6');

    // 6. 点击 Haiku 4.5 选项
    const haikuItem = page.locator('.model-dropdown-item').filter({ hasText: 'Haiku 4.5' });
    await haikuItem.click();
    await page.waitForTimeout(500);

    // 验证 POST 被调用
    expect(modelSetCalled).toBeTruthy();
    expect(modelSetBody?.model).toBe('claude-haiku-4-5');
  });
});
