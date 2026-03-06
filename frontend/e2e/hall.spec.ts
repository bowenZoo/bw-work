/**
 * 大厅页面 E2E 测试
 * 覆盖：页面加载、项目卡片、讨论卡片、创建弹窗
 */

import { test, expect } from './fixtures';
import { getToken, createTestProject, deleteTestProject } from './helpers/api';

test.describe('大厅页面', () => {
  test('已登录用户看到大厅主体', async ({ authedPage: page }) => {
    await expect(page.locator('.hall')).toBeVisible();
    // 头部标题
    await expect(page.locator('.hall-title')).toBeVisible();
    // 应有新讨论/新项目按钮
    await expect(page.locator('button').filter({ hasText: '新讨论' })).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '新项目' })).toBeVisible();
  });

  test('Tab 切换 - 讨论 / 项目', async ({ authedPage: page }) => {
    const tabs = page.locator('.hall-tab, [class*="tab"]').filter({ hasText: /讨论|项目/ });
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // 点击项目 Tab
    await tabs.filter({ hasText: '项目' }).first().click();
    // 项目列表容器应出现
    await expect(page.locator('[class*="project"], .project-list, .card-grid').first()).toBeVisible({ timeout: 5000 });
  });

  test('新建项目弹窗 - 打开与关闭', async ({ authedPage: page }) => {
    await page.locator('button').filter({ hasText: '新项目' }).click();
    // 弹窗出现
    const modal = page.locator('.dialog, [class*="modal"], [class*="overlay"]').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // 取消关闭
    const cancelBtn = modal.locator('button').filter({ hasText: /取消|关闭|Cancel/ }).first();
    await cancelBtn.click();
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });

  test('新建项目 - 填写表单并提交', async ({ authedPage: page, request }) => {
    const token = await getToken(page);
    const projectName = `E2E项目_${Date.now()}`;

    await page.locator('button').filter({ hasText: '新项目' }).click();
    const modal = page.locator('.dialog, [class*="modal"]').first();
    await expect(modal).toBeVisible();

    // 填写名称
    const nameInput = modal.locator('input[placeholder*="项目名"], input[type="text"]').first();
    await nameInput.fill(projectName);

    // 提交
    const submitBtn = modal.locator('button').filter({ hasText: /创建|确认|提交/ }).first();
    await submitBtn.click();

    // 应跳转到项目详情页 /project/:id
    await page.waitForURL(/\/project\//, { timeout: 10000 });
    await expect(page.locator('.project-detail')).toBeVisible();

    // 清理：通过 API 删除项目
    const projectId = page.url().split('/project/')[1].split('/')[0];
    await deleteTestProject(request, token, projectId);
  });

  test('新建讨论弹窗 - 打开后有主题输入框', async ({ authedPage: page }) => {
    await page.locator('button').filter({ hasText: '新讨论' }).click();
    const modal = page.locator('.dialog, [class*="modal"], [class*="overlay"]').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // 应有主题/话题输入框
    const topicInput = modal.locator('textarea, input').first();
    await expect(topicInput).toBeVisible();

    await page.keyboard.press('Escape');
  });

  test('项目卡片 - 点击跳转到项目详情', async ({ authedPage: page, request }) => {
    const token = await getToken(page);
    const projectId = await createTestProject(request, token, `E2E跳转测试_${Date.now()}`);

    // 刷新大厅，等待项目卡片出现
    await page.reload();
    await page.waitForLoadState('networkidle');

    // 切换到项目 Tab
    const projectTab = page.locator('.hall-tab, [class*="tab"]').filter({ hasText: '项目' }).first();
    await projectTab.click();

    // 找到刚创建的项目卡片并点击
    const card = page.locator('[class*="card"]').filter({ hasText: /E2E跳转测试/ }).first();
    await expect(card).toBeVisible({ timeout: 8000 });
    await card.click();

    await page.waitForURL(`/project/${projectId}`, { timeout: 10000 });
    await expect(page.locator('.project-detail')).toBeVisible();

    await deleteTestProject(request, token, projectId);
  });
});
