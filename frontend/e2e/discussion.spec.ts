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
    expect(body).toHaveProperty('discussions');
    expect(body).toHaveProperty('total');
    expect(Array.isArray(body.discussions)).toBeTruthy();
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
    expect(Array.isArray(body.agents)).toBeTruthy();
    expect(body.agents.length).toBeGreaterThan(0);
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
    await page.goto('/discussion/nonexistent-id-12345');
    // 要么显示错误状态，要么被路由守卫重定向
    await page.waitForTimeout(3000);
    const url = page.url();
    const isRedirected = url.endsWith('/') || url.includes('/hall') || !url.includes('nonexistent-id-12345');
    const hasError = await page.locator('[class*="error"], [class*="not-found"]').count() > 0;
    expect(isRedirected || hasError).toBeTruthy();
  });

  test('已完成讨论页 - 展示基本 UI 结构', async ({ authedPage: page, request }) => {
    const token = await getToken(page);

    // 先查询是否有已完成的讨论
    const listRes = await request.get(`${API_URL}/api/discussions?limit=10`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const list = await listRes.json();
    const completed = list.discussions?.find((d: any) => d.status === 'completed');

    if (!completed) {
      test.skip();
      return;
    }

    await page.goto(`/discussion/${completed.id}`);
    await page.waitForLoadState('networkidle');

    // 讨论页面应有议程面板或历史消息面板
    const hasPanel = await page.locator(
      '[class*="agenda"], [class*="history"], [class*="discussion-view"]'
    ).count() > 0;
    expect(hasPanel).toBeTruthy();
  });
});
