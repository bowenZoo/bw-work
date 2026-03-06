/**
 * E2E 测试辅助函数
 */

import type { Page, APIRequestContext } from '@playwright/test';

const API_URL = 'http://localhost:18000';

/**
 * 获取当前页面的 access_token（从 localStorage）
 */
export async function getToken(page: Page): Promise<string> {
  const raw = await page.evaluate(() => localStorage.getItem('bw_user_tokens'));
  if (!raw) throw new Error('未找到认证 token');
  return JSON.parse(raw).access_token;
}

/**
 * 通过 API 创建一个测试项目，返回项目 id
 */
export async function createTestProject(
  request: APIRequestContext,
  token: string,
  name = `E2E项目_${Date.now()}`
): Promise<string> {
  const res = await request.post(`${API_URL}/api/projects`, {
    data: { name, description: 'E2E 测试项目' },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok()) throw new Error(`创建项目失败: ${await res.text()}`);
  const data = await res.json();
  return data.id;
}

/**
 * 通过 API 删除测试项目（清理用）
 */
export async function deleteTestProject(
  request: APIRequestContext,
  token: string,
  projectId: string
): Promise<void> {
  await request.delete(`${API_URL}/api/projects/${projectId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

/**
 * 等待大厅页面加载完成（判断特征元素出现）
 */
export async function waitForHallReady(page: Page): Promise<void> {
  await page.waitForSelector('.hall', { timeout: 10000 });
}

/**
 * 等待讨论页面的历史消息面板出现
 */
export async function waitForDiscussionReady(page: Page): Promise<void> {
  await page.waitForSelector('[class*="discussion"]', { timeout: 10000 });
}
