import { test, expect } from '@playwright/test';

test.describe('Day Selector', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays 7 day tabs', async ({ page }) => {
    const tabs = page.locator('.day-tab');
    await expect(tabs).toHaveCount(7);
  });

  test('first tab shows "Aujourd\'hui" (Today)', async ({ page }) => {
    const firstTab = page.locator('.day-tab').first();
    await expect(firstTab).toContainText("Aujourd'hui");
    await expect(firstTab).toHaveAttribute('aria-selected', 'true');
  });

  test('clicking a day tab updates selection', async ({ page }) => {
    const secondTab = page.locator('.day-tab').nth(1);
    const firstTab = page.locator('.day-tab').first();

    // Click second tab
    await secondTab.click();

    // Second tab should now be selected
    await expect(secondTab).toHaveAttribute('aria-selected', 'true');
    await expect(firstTab).toHaveAttribute('aria-selected', 'false');
  });

  test('updates URL hash when selecting a day', async ({ page }) => {
    const secondTab = page.locator('.day-tab').nth(1);

    // Get the date from the tab
    const date = await secondTab.getAttribute('data-date');

    // Click the tab
    await secondTab.click();

    // Check URL hash
    await expect(page).toHaveURL(new RegExp(`#day-${date}`));
  });

  test('supports keyboard navigation', async ({ page }) => {
    const firstTab = page.locator('.day-tab').first();
    const secondTab = page.locator('.day-tab').nth(1);

    // Focus first tab
    await firstTab.focus();

    // Press right arrow
    await page.keyboard.press('ArrowRight');

    // Second tab should now be selected
    await expect(secondTab).toHaveAttribute('aria-selected', 'true');
  });

  test('displays French day abbreviations', async ({ page }) => {
    const tabs = page.locator('.day-tab');

    // French day abbreviations: Lun, Mar, Mer, Jeu, Ven, Sam, Dim
    const frenchDays = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

    // Check that at least some French day names appear (excluding "Aujourd'hui")
    const allTabsText = await tabs.allTextContents();
    const hasMatchingDay = frenchDays.some(day =>
      allTabsText.some(text => text.includes(day))
    );

    expect(hasMatchingDay).toBe(true);
  });

  test('displays French month abbreviations', async ({ page }) => {
    const tabs = page.locator('.day-tab');

    // French month abbreviations
    const frenchMonths = ['jan', 'fév', 'mar', 'avr', 'mai', 'juin', 'juil', 'août', 'sep', 'oct', 'nov', 'déc'];

    // Check that at least one French month abbreviation appears
    const allTabsText = await tabs.allTextContents();
    const hasMatchingMonth = frenchMonths.some(month =>
      allTabsText.some(text => text.toLowerCase().includes(month))
    );

    expect(hasMatchingMonth).toBe(true);
  });
});
