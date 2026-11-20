import { test, expect } from '@playwright/test';

async function openDownloadSettings(page, item) {
  await item.click({ button: 'right' });
  await page.getByRole('button', { name: 'Download Settings' }).click();
}

async function save(page) {
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.locator('.dialog')).toBeHidden();
}

test('shows the download progress of a chat and then its completion', async ({ page }) => {
  const sentMessages = [];
  page.on('websocket', (socket) => {
    socket.on('framesent', (frame) => sentMessages.push(JSON.parse(frame.payload)));
  });
  await page.goto('/');

  const items = page.locator('[data-testid^="chat-item-"]');
  await expect(items.first()).toBeVisible();
  for (const listItem of await items.all()) {
    await expect(listItem.locator('.download-info')).toHaveText(/⏳|✓/);
  }

  const testId = await items.first().getAttribute('data-testid');
  const item = page.getByTestId(testId);
  await openDownloadSettings(page, item);
  await page.getByLabel('Download Media').check();
  await save(page);

  const updates = sentMessages.filter((message) => message.method === 'update_chat');
  expect(updates.at(-1).params).toEqual({ id: Number(testId.replace('chat-item-', '')), settings: { media: true } });

  await item.click();
  const details = page.locator('.chat-details');
  await expect(item).toContainText('⏳');
  await expect(details).toContainText('The chat is being downloaded, please wait...');
  await expect(details).toContainText('Messages:');

  await expect(item).toContainText('✓', { timeout: 15_000 });
  await expect(item).not.toContainText('1,000');
  await expect(details).toContainText('The chat is downloaded');
  await expect(details).toContainText('1,000');
  await expect(details).toContainText('100/100');

  await page.getByRole('button', { name: /^Downloaded/ }).click();
  await expect(item).toBeVisible();
});

test('keeps the saved Download Media value', async ({ page }) => {
  await page.goto('/');

  const items = page.locator('[data-testid^="chat-item-"]');
  const item = page.getByTestId(await items.first().getAttribute('data-testid'));
  const checkbox = page.getByLabel('Download Media');

  await openDownloadSettings(page, item);
  await checkbox.uncheck();
  await save(page);
  await openDownloadSettings(page, item);
  await expect(checkbox).not.toBeChecked();

  await checkbox.check();
  await save(page);
  await openDownloadSettings(page, item);
  await expect(checkbox).toBeChecked();
});

test('reports a request when OpenClaw is not configured', async ({ page }) => {
  await page.goto('/');

  const items = page.locator('[data-testid^="chat-item-"]');
  await items.first().click();
  await page.getByLabel('Request').fill('Summarize\nthe decisions');
  await page.getByRole('button', { name: 'Submit' }).click();

  await expect(page.locator('.chat-details')).toContainText('OpenClaw is not configured');
  await expect(page.getByLabel('Request')).toHaveValue('Summarize\nthe decisions');
});
