/**
 * 大厅页面 E2E 测试
 * 覆盖：页面加载、项目卡片、讨论卡片、创建弹窗
 * 注意：所有创建数据的测试使用 try/finally 保证清理，即使测试失败也会删除数据
 */

import { test, expect } from './fixtures';
import { getToken, createTestProject, deleteTestProject } from './helpers/api';

const API_URL = 'http://localhost:18000';

test.describe('大厅页面', () => {
  test('已登录用户看到大厅主体', async ({ authedPage: page }) => {
    await expect(page.locator('.hall')).toBeVisible();
    await expect(page.locator('.hall-title')).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '新讨论' })).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '新项目' })).toBeVisible();
  });

  test('Tab 切换 - 讨论 / 项目', async ({ authedPage: page }) => {
    const tabs = page.locator('.hall-tab, [class*="tab"]').filter({ hasText: /讨论|项目/ });
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(2);

    await tabs.filter({ hasText: '项目' }).first().click();
    await expect(page.locator('[class*="project"], .project-list, .card-grid').first()).toBeVisible({ timeout: 5000 });
  });

  test('新建项目弹窗 - 打开与关闭', async ({ authedPage: page }) => {
    await page.locator('button').filter({ hasText: '新项目' }).click();
    const modal = page.locator('.dialog, [class*="modal"], [class*="overlay"]').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    const cancelBtn = modal.locator('button').filter({ hasText: /取消|关闭|Cancel/ }).first();
    await cancelBtn.click();
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });

  test('新建项目 - 填写表单并提交后跳转概念孵化讨论', async ({ authedPage: page, request }) => {
    const token = await getToken(page);
    let createdProjectId: string | null = null;

    try {
      await page.locator('button').filter({ hasText: '新项目' }).click();
      const modal = page.locator('.dialog, [class*="modal"]').first();
      await expect(modal).toBeVisible();

      const nameInput = modal.locator('input[placeholder*="项目名"], input[type="text"]').first();
      await nameInput.fill(`E2E项目_${Date.now()}`);

      const submitBtn = modal.locator('button').filter({ hasText: /创建|确认|提交/ }).first();
      await submitBtn.click();

      await page.waitForURL(/\/discussion\//, { timeout: 12000 });
      const discussionId = page.url().split('/discussion/')[1].split('/')[0];
      expect(discussionId).toBeTruthy();

      const discRes = await request.get(`${API_URL}/api/discussions/${discussionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (discRes.ok()) {
        const discData = await discRes.json();
        createdProjectId = discData.project_id ?? null;
      }
    } finally {
      if (createdProjectId) {
        await deleteTestProject(request, token, createdProjectId);
      }
    }
  });

  test('新建讨论弹窗 - 打开后有主题输入框', async ({ authedPage: page }) => {
    await page.locator('button').filter({ hasText: '新讨论' }).click();
    const modal = page.locator('.dialog, [class*="modal"], [class*="overlay"]').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    const topicInput = modal.locator('textarea, input').first();
    await expect(topicInput).toBeVisible();

    await page.keyboard.press('Escape');
  });

  test('项目卡片 - 点击跳转到项目详情', async ({ authedPage: page, request }) => {
    const token = await getToken(page);
    const projectId = await createTestProject(request, token, `E2E跳转测试_${Date.now()}`);

    try {
      await page.reload();
      await page.waitForLoadState('networkidle');

      const projectTab = page.locator('.hall-tab, [class*="tab"]').filter({ hasText: '项目' }).first();
      await projectTab.click();

      const card = page.locator('[class*="card"]').filter({ hasText: /E2E跳转测试/ }).first();
      await expect(card).toBeVisible({ timeout: 8000 });
      await card.click();

      await page.waitForURL(/\/project\//, { timeout: 10000 });
      await expect(page.locator('.project-detail')).toBeVisible({ timeout: 10000 });
    } finally {
      await deleteTestProject(request, token, projectId);
    }
  });
});
