/**
 * 概念孵化流程 E2E 测试
 * 验收：创建项目 → API 返回 concept_discussion_id → 自动跳转讨论页 → 讨论配置正确
 */

import { test, expect } from './fixtures';
import { getToken, deleteTestProject } from './helpers/api';

const API_URL = 'http://localhost:18000';

test.describe('概念孵化流程', () => {
  test('API：创建项目返回 concept_discussion_id', async ({ authedPage: page, request }) => {
    const token = await getToken(page);

    const projRes = await request.post(`${API_URL}/api/projects`, {
      data: { name: `孵化API验收_${Date.now()}`, description: '验证concept_discussion_id字段' },
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(projRes.ok()).toBeTruthy();
    const projData = await projRes.json();

    // 必须返回 concept_discussion_id
    expect(projData.concept_discussion_id).toBeTruthy();
    expect(projData.concept_discussion_id.length).toBeGreaterThan(8);

    // 清理
    await deleteTestProject(request, token, projData.id);
  });

  test('API：概念孵化讨论包含正确的 agent 和主持人配置', async ({ authedPage: page, request }) => {
    const token = await getToken(page);

    // 创建项目
    const projRes = await request.post(`${API_URL}/api/projects`, {
      data: { name: `孵化Agent验收_${Date.now()}`, description: '验证agent配置' },
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(projRes.ok()).toBeTruthy();
    const projData = await projRes.json();
    expect(projData.concept_discussion_id).toBeTruthy();

    // 查询讨论详情
    const discRes = await request.get(`${API_URL}/api/discussions/${projData.concept_discussion_id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(discRes.ok()).toBeTruthy();
    const discData = await discRes.json();

    // 验证参与者
    const agents: string[] = discData.agents || [];
    expect(agents).toContain('creative_director');
    expect(agents).toContain('lead_planner');
    expect(agents).toContain('market_director');

    // 验证主持人
    expect(discData.moderator_role).toBe('creative_director');

    // 验证 target_type
    expect(discData.target_type).toBe('stage');

    // 验证关联项目
    expect(discData.project_id).toBe(projData.id);

    // 清理
    await deleteTestProject(request, token, projData.id);
  });

  test('UI：创建项目后自动跳转概念孵化讨论页', async ({ authedPage: page, request }) => {
    const token = await getToken(page);
    const projectName = `孵化UI验收_${Date.now()}`;

    // 打开新项目弹窗
    await page.locator('button').filter({ hasText: '新项目' }).click();
    const modal = page.locator('.dialog, [class*="modal"]').first();
    await expect(modal).toBeVisible({ timeout: 5000 });

    // 填写项目名
    const nameInput = modal.locator('input[placeholder*="项目名"], input[type="text"]').first();
    await nameInput.fill(projectName);

    // 可选：填写描述
    const descInput = modal.locator('textarea').first();
    if (await descInput.isVisible()) {
      await descInput.fill('概念孵化E2E验收');
    }

    // 提交
    const submitBtn = modal.locator('button').filter({ hasText: /创建|确认|提交/ }).first();
    await submitBtn.click();

    // 验证：跳转到 /discussion/:id
    await page.waitForURL(/\/discussion\//, { timeout: 12000 });
    const url = page.url();
    const discussionId = url.split('/discussion/')[1]?.split('/')[0];
    expect(discussionId).toBeTruthy();
    expect(discussionId.length).toBeGreaterThan(8);

    // 讨论页面应渲染出来
    await expect(page.locator('[class*="discussion"]').first()).toBeVisible({ timeout: 8000 });

    // 验证讨论元数据正确
    const discRes = await request.get(`${API_URL}/api/discussions/${discussionId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(discRes.ok()).toBeTruthy();
    const discData = await discRes.json();
    expect(discData.moderator_role).toBe('creative_director');
    expect(discData.project_id).toBeTruthy();

    // 清理
    await deleteTestProject(request, token, discData.project_id);
  });
});
