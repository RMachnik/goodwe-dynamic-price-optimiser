import { test, expect, devices } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';

test.describe('Dashboard Core E2E', () => {

    test('should show login page and handle authentication', async ({ page }) => {
        await page.goto(`${BASE_URL}/login`);

        // Check elements
        await expect(page.locator('h1')).toContainText('Welcome Back');

        // Fill form
        await page.fill('input[type="email"]', 'admin@example.com');
        await page.fill('input[type="password"]', 'admin123');

        // Click submit and wait for navigation
        await Promise.all([
            page.waitForURL(`${BASE_URL}/`),
            page.click('button[type="submit"]')
        ]);


        // Should be redirected to dashboard
        await expect(page).toHaveURL(`${BASE_URL}/`);

        // Wait for and verify dashboard content loaded
        await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
        await expect(page.locator('h1')).toContainText('Fleet Overview');
    });

    test('should toggle theme mode', async ({ page }) => {
        // Login first
        await page.goto(`${BASE_URL}/login`);
        await page.fill('input[type="email"]', 'admin@example.com');
        await page.fill('input[type="password"]', 'admin123');
        await Promise.all([
            page.waitForURL(`${BASE_URL}/`),
            page.click('button[type="submit"]')
        ]);

        const html = page.locator('html');

        // Default should be dark
        await expect(html).toHaveClass(/dark/);

        // Find and click theme toggle (look for Moon or Sun icon or "Dark Mode" text)
        const themeButton = page.locator('button:has-text("Dark Mode"), button:has-text("Light Mode")').first();
        await themeButton.click();

        // Should switch to light mode
        await expect(html).toHaveClass(/light/);

        // Reload and check persistence
        await page.reload();
        await expect(html).toHaveClass(/light/);
    });

    test('should render mobile bottom navigation on small screens', async ({ page }) => {
        await page.setViewportSize(devices['iPhone 13'].viewport);

        // Login
        await page.goto(`${BASE_URL}/login`);
        await page.fill('input[type="email"]', 'admin@example.com');
        await page.fill('input[type="password"]', 'admin123');
        await Promise.all([
            page.waitForURL(`${BASE_URL}/`),
            page.click('button[type="submit"]')
        ]);

        // Desktop sidebar should be hidden (translated off-screen)
        const sidebar = page.locator('aside');
        await expect(sidebar).toHaveClass(/-translate-x-full/);

        // Bottom nav should be visible
        const bottomNav = page.locator('nav').last();
        await expect(bottomNav).toBeVisible();
    });
});
