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

  test('页面加载 - 显示项目名和流程列', async ({ authedPage: page }) => {
    // 项目名显示在 .header-title 而非 h1
    await expect(page.locator('.header-title')).toBeVisible();
    // 流程看板使用 .pipeline 容器
    await expect(page.locator('.pipeline')).toBeVisible();
    // 至少有一个阶段列
    const stages = page.locator('.pipeline-col');
    expect(await stages.count()).toBeGreaterThanOrEqual(1);
  });

  test('阶段列显示阶段名称', async ({ authedPage: page }) => {
    const firstCol = page.locator('.pipeline-col').first();
    await expect(firstCol).toBeVisible();
    // 阶段名称在 .col-name 里
    await expect(firstCol.locator('.col-name')).toBeVisible();
  });

  test('成员管理弹窗 - 打开与关闭', async ({ authedPage: page }) => {
    // 成员管理按钮通过 title 属性标识
    const memberBtn = page.locator('button[title="成员管理"]').first();
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
    // 直接等待 "新讨论" 按钮出现（依赖 canEdit+stage.status=active 同时为真）
    await page.waitForSelector('.new-btn', { timeout: 12000 });
    const newDiscBtn = page.locator('.new-btn').filter({ hasText: '新讨论' }).first();
    await expect(newDiscBtn).toBeVisible({ timeout: 5000 });
    await newDiscBtn.click();

    const dialog = page.locator('.dialog-enhanced').first();
    await expect(dialog).toBeVisible({ timeout: 5000 });
    await expect(dialog.locator('textarea').first()).toBeVisible();

    await dialog.locator('button').filter({ hasText: /取消|关闭/ }).first().click();
    await expect(dialog).not.toBeVisible({ timeout: 3000 });
  });

  test('返回大厅按钮', async ({ authedPage: page }) => {
    // 面包屑中的"大厅"链接始终可见
    const breadcrumbLink = page.locator('.bc-link').filter({ hasText: '大厅' }).first();
    await expect(breadcrumbLink).toBeVisible();
    await breadcrumbLink.click();
    // SPA 路由 pushState 不触发 load 事件，直接等待大厅容器出现
    await expect(page.locator('.hall')).toBeVisible({ timeout: 5000 });
  });
});
