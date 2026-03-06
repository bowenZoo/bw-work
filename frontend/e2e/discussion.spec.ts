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
