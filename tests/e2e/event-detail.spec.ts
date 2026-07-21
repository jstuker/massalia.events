import { test, expect } from '@playwright/test';

test.describe('Event Detail Pages', () => {
  test('events listing page loads', async ({ page }) => {
    await page.goto('/events/');

    await expect(page.locator('main')).toBeVisible();
  });

  // Events expire (expiryDate in front matter), so hardcoded event URLs
  // eventually 404. Navigate via the first event link on the listing instead.
  async function gotoFirstEvent(page) {
    await page.goto('/events/');
    const href = await page
      .locator('main a[href*="/events/2"]')
      .first()
      .getAttribute('href');
    expect(href).toBeTruthy();
    await page.goto(href!);
  }

  test('individual event page loads correctly', async ({ page }) => {
    await gotoFirstEvent(page);

    // Check page loads with a real event title, not the 404 page
    await expect(page.locator('main')).toBeVisible();
    const heading = page.getByRole('heading', { level: 1 });
    await expect(heading).not.toBeEmpty();
    await expect(heading).not.toContainText(/Page non trouvée/i);
  });

  test('event page displays event metadata', async ({ page }) => {
    await gotoFirstEvent(page);

    // Check for category or location link
    const hasCategory = await page.locator('a[href*="/categories/"]').count();
    const hasLocation = await page.locator('a[href*="/locations/"]').count();

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
