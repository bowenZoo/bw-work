/**
 * 共享 Fixtures：提供已登录状态的 page，避免每个测试重复登录
 *
 * 用法：
 *   import { test, expect } from '../fixtures';
 *   test('...', async ({ authedPage }) => { ... });
 */

import { test as base, expect, type Page } from '@playwright/test';

const BASE_URL = 'http://localhost:18001';
const API_URL = 'http://localhost:18000';

// 测试用账号（在 .env.test 或环境变量里覆盖）
export const TEST_USER = {
  username: process.env.TEST_USERNAME ?? 'e2e_test_user',
  password: process.env.TEST_PASSWORD ?? 'Test@123456',
  display_name: 'E2E测试用户',
};

/**
 * 通过 API 直接注册/登录，将 token 注入 localStorage，
 * 跳过 UI 登录流程（更快、更稳定）
 */
export async function loginViaApi(page: Page): Promise<void> {
  // 先尝试登录，失败则注册
  let tokens: { access_token: string; refresh_token: string; user: any } | null = null;

  const loginRes = await page.request.post(`${API_URL}/api/auth/login`, {
    data: { username: TEST_USER.username, password: TEST_USER.password },
  });

  if (loginRes.ok()) {
    tokens = await loginRes.json();
  } else {
    // 账号不存在则自动注册
    const regRes = await page.request.post(`${API_URL}/api/auth/register`, {
      data: {
        username: TEST_USER.username,
        password: TEST_USER.password,
        display_name: TEST_USER.display_name,
      },
    });
    expect(regRes.ok(), `注册失败: ${await regRes.text()}`).toBeTruthy();
    tokens = await regRes.json();
  }

  // 注入 token 到 localStorage（需要先访问一次同源页面）
  await page.goto(BASE_URL);
  await page.evaluate((t) => {
    localStorage.setItem('bw_user_tokens', JSON.stringify({
      access_token: t.access_token,
      refresh_token: t.refresh_token,
    }));
  }, tokens!);

  // 刷新页面使 store 读取 token
  await page.reload();
  await page.waitForLoadState('networkidle');
}

// 扩展 test fixture，提供已认证的 page
type Fixtures = {
  authedPage: Page;
};

export const test = base.extend<Fixtures>({
  authedPage: async ({ page }, use) => {
    await loginViaApi(page);
    await use(page);
  },
});

export { expect };
