import { test, expect } from '@playwright/test';

test.describe('Analytics Features', () => {
    test.beforeEach(async ({ page }) => {
        // 1. Mock Authentication
        await page.route('**/auth/token', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ access_token: 'fake-jwt-token' })
            });
        });

        await page.route('**/auth/me', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ email: 'admin@example.com', role: 'admin' })
            });
        });

        // 2. Mock Nodes List
        await page.route('**/nodes', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    { id: 'node-123', hardware_id: 'rasp-01', name: 'Test Node', is_online: true }
                ])
            });
        });

        // 3. Mock Daily Savings Stats
        await page.route('**/stats/daily-savings/**', async route => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    { date: '2026-01-01', savings_pln: 5.5 },
                    { date: '2026-01-02', savings_pln: 12.0 },
                    { date: '2026-01-03', savings_pln: -2.0 }
                ])
            });
        });

        // Login Flow
        await page.goto('/login');
        await page.fill('input[type="email"]', 'admin@example.com');
        await page.fill('input[type="password"]', 'password');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL('/');
    });

    test('should display daily savings chart on node detail page', async ({ page }) => {
        // Navigate to Node Detail
        await page.click('text=Test Node');

        // Check URL
        await expect(page).toHaveURL(/\/nodes\/node-123/);

        // Check for "Daily Savings" Card in top grid
        await expect(page.locator('text=Daily Savings').first()).toBeVisible();

        // Check for "Cost Savings" Chart Card
        const chartCard = page.locator('.glass-card', { hasText: 'Cost Savings' });
        await expect(chartCard).toBeVisible();

        // Verify Total Saved text (Sum of mocked data: 5.5 + 12 - 2 = 15.5)
        await expect(chartCard).toContainText('+15.50 PLN');

        // Verify Chart presence (Recharts renders a surface/svg)
        await expect(chartCard.locator('.recharts-surface')).toBeVisible();

        // Verify columns (bars) exist
        // Recharts renders paths for bars. We expect 3 distinct paths or groups.
        // This is hard to assert exactly without snapshot testing, but existence is key.
        const bars = chartCard.locator('.recharts-bar-rectangle');
        await expect(bars).toHaveCount(3);
    });
});
