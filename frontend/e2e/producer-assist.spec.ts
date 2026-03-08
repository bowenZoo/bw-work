/**
 * 决策卡选项 E2E 测试
 *
 * 验证：producer-assist API 始终返回非空答案选项，
 * 决策卡不会退化成空白自定义输入框。
 *
 * 使用 WebMCP bridge（window.__bw）完成全部操作，无需 DOM 选择器。
 */

import { test, expect } from './fixtures';
import { getToken } from './helpers/api';

const API_URL = 'http://localhost:18000';
const DISCUSSION_ID = '8945cf45-2883-4934-8e68-55c49d5f4342'; // 昆虫三消 — 概念孵化

// ── 工具函数 ──────────────────────────────────────────────────────────────────

/** 等待 bridge 注册完成 */
async function waitForBridge(page: import('@playwright/test').Page) {
  await page.waitForFunction(() => !!(window as any).__bw, { timeout: 10000 });
}

/** 通过 bridge 导航到讨论页并等待 __bwDiscussion 挂载 */
async function navigateToDiscussion(page: import('@playwright/test').Page, id: string) {
  await page.evaluate((discussionId) => {
    (window as any).__vue_router.push(`/discussion/${discussionId}`);
  }, id);
  // 等待 __bwDiscussion 由 DiscussionView 挂载
  await page.waitForFunction(() => !!(window as any).__bwDiscussion, { timeout: 8000 });
  await page.waitForTimeout(500); // 等数据加载完毕
}

// ── 测试组 1：API 层验证（不依赖讨论页 UI）────────────────────────────────────

test.describe('producer-assist API', () => {

  test('返回结构合法：mode=questions，questions 非空', async ({ request, authedPage: page }) => {
    const token = await getToken(page);
    const res = await request.post(`${API_URL}/api/discussions/${DISCUSSION_ID}/producer-assist`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.mode).toBe('questions');
    expect(Array.isArray(body.questions)).toBeTruthy();
    expect(body.questions.length).toBeGreaterThan(0);
  });

  test('每道题都有至少 1 条答案选项', async ({ request, authedPage: page }) => {
    const token = await getToken(page);
    const res = await request.post(`${API_URL}/api/discussions/${DISCUSSION_ID}/producer-assist`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    });
    const body = await res.json();
    for (const q of body.questions) {
      expect(
        Array.isArray(q.answers) && q.answers.length >= 1,
        `问题「${q.question?.slice(0, 40)}」的 answers 为空`
      ).toBeTruthy();
    }
  });

  test('heuristic 降级时也提供默认答案（不返回空 answers）', async ({ request, authedPage: page }) => {
    // 发起两次调用：第一次消耗缓存的显式问题，第二次走 A2 heuristic 路径
    const token = await getToken(page);
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    await request.post(`${API_URL}/api/discussions/${DISCUSSION_ID}/producer-assist`, { headers });
    const res2 = await request.post(`${API_URL}/api/discussions/${DISCUSSION_ID}/producer-assist`, { headers });
    expect(res2.ok()).toBeTruthy();
    const body = await res2.json();
    // 无论走哪条路径，answers 不能为空数组
    if (body.mode === 'questions' && body.questions?.length > 0) {
      for (const q of body.questions) {
        expect(
          (q.answers || []).length >= 1,
          `heuristic 路径下问题「${q.question?.slice(0, 40)}」仍返回空 answers`
        ).toBeTruthy();
      }
    }
  });

});

// ── 测试组 2：Bridge 层验证（读取实时状态）────────────────────────────────────

test.describe('bridge bw_get_producer_assist', () => {

  test('bridge 工具返回 all_have_answers=true', async ({ authedPage: page }) => {
    await waitForBridge(page);

    const result = await page.evaluate(async (id) => {
      const bw = (window as any).__bw;
      return await bw.bw_get_producer_assist({ id });
    }, DISCUSSION_ID);

    expect(result.error).toBeUndefined();
    expect(result.question_count).toBeGreaterThan(0);
    expect(result.all_have_answers).toBe(true);
  });

  test('bridge 工具返回的每道题 answer_count >= 1', async ({ authedPage: page }) => {
    await waitForBridge(page);

    const result = await page.evaluate(async (id) => {
      return await (window as any).__bw.bw_get_producer_assist({ id });
    }, DISCUSSION_ID);

    for (const q of result.questions ?? []) {
      expect(
        q.answer_count >= 1,
        `bridge: 问题「${q.question?.slice(0, 40)}」answer_count=${q.answer_count}`
      ).toBeTruthy();
    }
  });

});

// ── 测试组 3：讨论页 UI 验证（决策卡渲染）────────────────────────────────────

test.describe('讨论页决策卡 UI', () => {

  test('进入等待决策的讨论页 — __bwDiscussion 上下文正确反映状态', async ({ authedPage: page }) => {
    await waitForBridge(page);
    await navigateToDiscussion(page, DISCUSSION_ID);

    const ctx = await page.evaluate(() => {
      const d = (window as any).__bwDiscussion;
      return {
        id: d?.discussion?.id,
        status: d?.discussion?.status,
        is_waiting_decision: d?.isWaitingDecision,
        checkpoint_count: (d?.checkpoints || []).length,
        pending: (d?.checkpoints || []).filter((c: any) => c.type === 'decision' && !c.responded_at).length,
      };
    });

    expect(ctx.id).toBe(DISCUSSION_ID);
    expect(ctx.status).toBe('waiting_decision');
    expect(ctx.is_waiting_decision).toBe(true);
    expect(ctx.pending).toBeGreaterThan(0);
  });

  test('决策卡区域显示选项按钮，不显示空白文本框', async ({ authedPage: page }) => {
    await waitForBridge(page);
    await navigateToDiscussion(page, DISCUSSION_ID);

    // 等待决策卡渲染
    await page.waitForSelector('.pds-card', { timeout: 8000 });

    // 有选项按钮
    const optionButtons = page.locator('.pds-option');
    await expect(optionButtons.first()).toBeVisible({ timeout: 5000 });
    const count = await optionButtons.count();
    expect(count).toBeGreaterThanOrEqual(1);

    // 自定义文本框不应自动展开（没有 answers 时才会展开）
    const textarea = page.locator('.pds-textarea');
    await expect(textarea).not.toBeVisible();
  });

  test('点击选项后「完成并发送」按钮变为可用', async ({ authedPage: page }) => {
    await waitForBridge(page);
    await navigateToDiscussion(page, DISCUSSION_ID);

    await page.waitForSelector('.pds-card', { timeout: 8000 });
    await page.waitForSelector('.pds-option', { timeout: 5000 });

    // 点击第一个选项
    await page.locator('.pds-option').first().click();

    // 发送按钮变为可用
    const submitBtn = page.locator('.pds-btn-submit');
    await expect(submitBtn).toBeEnabled({ timeout: 2000 });
  });

  test('重新生成后决策卡仍有答案选项', async ({ authedPage: page }) => {
    await waitForBridge(page);
    await navigateToDiscussion(page, DISCUSSION_ID);

    await page.waitForSelector('.pds-card', { timeout: 8000 });

    // 点击重新生成
    await page.locator('button[title="重新生成"]').click();

    // 等待 loading 消失，新选项出现
    await page.waitForSelector('.pds-option', { timeout: 15000 });

    const count = await page.locator('.pds-option').count();
    expect(count).toBeGreaterThanOrEqual(1);

    // 仍不应有自动展开的文本框
    await expect(page.locator('.pds-textarea')).not.toBeVisible();
  });

});
