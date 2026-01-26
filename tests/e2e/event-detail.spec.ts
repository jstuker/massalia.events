import { test, expect } from '@playwright/test';

test.describe('Event Detail Pages', () => {
  test('events listing page loads', async ({ page }) => {
    await page.goto('/events/');

    await expect(page.locator('main')).toBeVisible();
  });

  test('individual event page loads correctly', async ({ page }) => {
    // Navigate to a known event page
    await page.goto('/events/2026/01/27/concert-la-friche/');

    // Check page loads
    await expect(page.locator('main')).toBeVisible();

    // Check for event title in heading
    await expect(page.getByRole('heading', { level: 1 })).toContainText(/Concert/i);
  });

  test('event page displays event metadata', async ({ page }) => {
    await page.goto('/events/2026/01/27/concert-la-friche/');

    // Check for category or location link
    const hasCategory = await page.getByText(/musique/i).count();
    const hasLocation = await page.getByText(/friche/i).count();

    // Should have at least one of these
    expect(hasCategory + hasLocation).toBeGreaterThan(0);
  });

  test('categories page loads', async ({ page }) => {
    await page.goto('/categories/');

    await expect(page.locator('main')).toBeVisible();
  });

  test('locations page loads', async ({ page }) => {
    await page.goto('/locations/');

    await expect(page.locator('main')).toBeVisible();
  });

  test('individual category page loads', async ({ page }) => {
    await page.goto('/categories/musique/');

    await expect(page.locator('main')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1 })).toContainText(/Musique/i);
  });

  test('individual location page loads', async ({ page }) => {
    await page.goto('/locations/la-friche/');

    await expect(page.locator('main')).toBeVisible();
  });

  test('dates listing page loads', async ({ page }) => {
    await page.goto('/dates/');

    await expect(page.locator('main')).toBeVisible();
  });
});
