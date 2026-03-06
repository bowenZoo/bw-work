/**
 * 项目详情页 E2E 测试
 * 覆盖：页面加载、阶段显示、创建讨论、成员弹窗
 */

import { test, expect } from './fixtures';
import { getToken, createTestProject, deleteTestProject } from './helpers/api';

test.describe('项目详情页', () => {
  let projectId: string;

  test.beforeEach(async ({ authedPage: page, request }) => {
    const token = await getToken(page);
    projectId = await createTestProject(request, token, `E2E详情_${Date.now()}`);
    // 使用 SPA 内部路由跳转，避免全页刷新导致 user store 重新初始化的竞态问题
    await page.evaluate((id) => {
      (window as any).__vue_router.push(`/project/${id}`)
    }, projectId);
    await page.waitForSelector('.project-detail', { timeout: 15000 });
  });

  test.afterEach(async ({ authedPage: page, request }) => {
    const token = await getToken(page);
    await deleteTestProject(request, token, projectId);
  });

  test('页面加载 - 显示项目名和阶段列表', async ({ authedPage: page }) => {
    await expect(page.locator('.pd-header h1')).toBeVisible();
    await expect(page.locator('.stages')).toBeVisible();
    // 至少有一个阶段
    const stages = page.locator('.stage-section');
    expect(await stages.count()).toBeGreaterThanOrEqual(1);
  });

  test('阶段折叠/展开', async ({ authedPage: page }) => {
    const firstStageHeader = page.locator('.stage-header').first();
    const firstStageBody = page.locator('.stage-body').first();

    // 初始展开
    await expect(firstStageBody).not.toHaveClass(/stage-body-collapsed/);

    // 点击折叠
    await firstStageHeader.click();
    await expect(firstStageBody).toHaveClass(/stage-body-collapsed/, { timeout: 3000 });

    // 再次点击展开
    await firstStageHeader.click();
    await expect(firstStageBody).not.toHaveClass(/stage-body-collapsed/, { timeout: 3000 });
  });

  test('成员管理弹窗 - 打开与关闭', async ({ authedPage: page }) => {
    const memberBtn = page.locator('button').filter({ hasText: '成员' }).first();
    await expect(memberBtn).toBeVisible();
    await memberBtn.click();

    const dialog = page.locator('.dialog-wide').first();
    await expect(dialog).toBeVisible({ timeout: 5000 });
    // 标题含"成员"
    await expect(dialog.locator('h3')).toContainText('成员');

    await dialog.locator('button').filter({ hasText: /关闭|取消/ }).first().click();
    await expect(dialog).not.toBeVisible({ timeout: 3000 });
  });

  test('在活跃阶段新建讨论弹窗', async ({ authedPage: page }) => {
    // 找"+ 新讨论"按钮（在活跃阶段的 stage-actions 里）
    const newDiscBtn = page.locator('.stage-actions button').filter({ hasText: '新讨论' }).first();
    await expect(newDiscBtn).toBeVisible({ timeout: 5000 });
    await newDiscBtn.click();

    const dialog = page.locator('.dialog-enhanced').first();
    await expect(dialog).toBeVisible({ timeout: 5000 });
    await expect(dialog.locator('textarea')).toBeVisible();

    await dialog.locator('button').filter({ hasText: /取消|关闭/ }).first().click();
    await expect(dialog).not.toBeVisible({ timeout: 3000 });
  });

  test('返回大厅按钮', async ({ authedPage: page }) => {
    await page.locator('.back-btn').first().click();
    // SPA 路由 pushState 不触发 load 事件，直接等待大厅容器出现
    await expect(page.locator('.hall')).toBeVisible({ timeout: 5000 });
  });
});
