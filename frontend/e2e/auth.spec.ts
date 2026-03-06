/**
 * 认证流程 E2E 测试
 * 覆盖：注册、登录、登出
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:18001';
const API_URL = 'http://localhost:18000';

// 每次运行用不同用户名，避免冲突
const unique = Date.now();
const NEW_USER = {
  username: `e2e_new_${unique}`,
  password: 'Test@123456',
  display_name: '新注册用户',
};

test.describe('认证流程', () => {
  test('注册新账号 - 成功后跳转大厅', async ({ page }) => {
    // 直接导航到 /login 页（LoginView）
    await page.goto(`${BASE_URL}/login`);

    // 切换到注册 Tab（LoginView 里 tab 是 div.tab，不是 button）
    const registerTab = page.locator('.tab').filter({ hasText: '注册' }).first();
    await expect(registerTab).toBeVisible({ timeout: 8000 });
    await registerTab.click();

    // 填写注册表单
    const usernameInput = page.locator('input[placeholder*="用户名"]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    const confirmPasswordInput = page.locator('input[placeholder*="再次"]').first();
    await usernameInput.fill(NEW_USER.username);
    await passwordInput.fill(NEW_USER.password);
    await confirmPasswordInput.fill(NEW_USER.password);

    // 提交
    const submitBtn = page.locator('button').filter({ hasText: /^注册$/ }).first();
    await submitBtn.click();

    // 注册成功后应跳回大厅
    await page.waitForURL(`${BASE_URL}/`, { timeout: 10000 });
    await expect(page.locator('.hall')).toBeVisible();
  });

  test('登录已有账号 - 通过 API 直接验证', async ({ request }) => {
    // 先注册
    await request.post(`${API_URL}/api/auth/register`, {
      data: {
        username: `e2e_login_${unique}`,
        password: 'Test@654321',
        display_name: '登录测试',
      },
    });

    // 再登录
    const res = await request.post(`${API_URL}/api/auth/login`, {
      data: { username: `e2e_login_${unique}`, password: 'Test@654321' },
    });
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body).toHaveProperty('access_token');
    expect(body).toHaveProperty('refresh_token');
    expect(body.user.username).toBe(`e2e_login_${unique}`);
  });

  test('密码错误 - 登录失败返回 401', async ({ request }) => {
    const res = await request.post(`${API_URL}/api/auth/login`, {
      data: { username: 'nonexistent_user_xyz', password: 'wrongpassword' },
    });
    expect(res.status()).toBe(401);
  });

  test('已登录用户访问 /api/auth/me 返回用户信息', async ({ request }) => {
    // 注册获取 token
    const regRes = await request.post(`${API_URL}/api/auth/register`, {
      data: {
        username: `e2e_me_${unique}`,
        password: 'Test@me1234',
        display_name: 'Me测试',
      },
    });
    const { access_token } = await regRes.json();

    // 访问 /me
    const meRes = await request.get(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(meRes.ok()).toBeTruthy();
    const me = await meRes.json();
    expect(me.username).toBe(`e2e_me_${unique}`);
    expect(me).toHaveProperty('id');
    expect(me).toHaveProperty('role');
  });

  test('token 刷新 - 用 refresh_token 换新 access_token', async ({ request }) => {
    const regRes = await request.post(`${API_URL}/api/auth/register`, {
      data: {
        username: `e2e_refresh_${unique}`,
        password: 'Test@refresh1',
      },
    });
    const { refresh_token } = await regRes.json();

    const refreshRes = await request.post(`${API_URL}/api/auth/refresh`, {
      data: { refresh_token },
    });
    expect(refreshRes.ok()).toBeTruthy();
    const refreshed = await refreshRes.json();
    expect(refreshed).toHaveProperty('access_token');
  });
});
