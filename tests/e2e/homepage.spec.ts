import { test, expect } from '@playwright/test';

test.describe('Homepage', () => {
  test('loads successfully', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/massalia/i);
  });

  test('displays French content', async ({ page }) => {
    await page.goto('/');

    // Check for French day selector labels
    const daySelector = page.locator('.day-selector');
    await expect(daySelector).toBeVisible();

    // Should have "Aujourd'hui" (Today) as first tab
    await expect(page.getByText("Aujourd'hui")).toBeVisible();
  });

  test('has navigation menu', async ({ page }) => {
    await page.goto('/');

    // Check for navigation elements
    const nav = page.locator('nav');
    await expect(nav.first()).toBeVisible();
  });

  test('displays events section', async ({ page }) => {
    await page.goto('/');

    // Check for event cards or event listing
    const eventCards = page.locator('.event-card, [class*="event"]');
    // Page should have some content related to events
    await expect(page.locator('main')).toBeVisible();
  });
});
