import { expect, test } from "@playwright/test";

test("real corpus, synchronized filters, complete downloads, and empty state", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("./");
  await expect(page.getByRole("heading", { name: "The words between the parties." })).toBeVisible();
  const response = await page.request.get("./data/dataset.json");
  const dataset = await response.json();
  await expect(page.getByRole("status")).toContainText(`${dataset.ads.length} records`);
  await page.getByLabel("Chambers", { exact: true }).selectOption("Senate");
  await page.getByLabel("Parties", { exact: true }).selectOption("R");
  const included = dataset.ads.filter((ad: { chamber: string; alignment: string }) =>
    ad.chamber === "Senate" && ad.alignment === "R");
  await expect(page.getByRole("status")).toContainText(`${included.length} records`);
  const pendingDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download JSON" }).click();
  const download = await pendingDownload;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk);
  const exported = JSON.parse(Buffer.concat(chunks).toString());
  expect(exported.ads).toHaveLength(included.length);
  expect(exported.ads[0].text).toBe(included[0].text);
  expect(exported.ads[0].segments.length).toBeGreaterThan(0);
  await page.getByLabel("Search the ad text", { exact: true }).fill("not-a-real-message-xyz");
  await expect(page.getByRole("status")).toContainText("0 records");
  await expect(page.getByText("No ads match these filters.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page.getByRole("status")).toContainText(`${dataset.ads.length} records`);
  await page.getByRole("button", { name: "Read the ad in context" }).first().click();
  await expect(page.locator(".ad-card.selected .transcript")).toHaveClass(/open/);
  expect(errors).toEqual([]);
});

test("mobile layout, keyboard access, static report and base-path assets", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./");
  await expect(page.getByRole("heading", { name: "The ad library." })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to analysis" })).toBeFocused();
  const report = await page.request.get("./report.html");
  expect(report.ok()).toBe(true);
  expect(await report.text()).toContain("Download the complete text and evidence");
  const csv = await page.request.get("./data/ads.csv");
  expect(csv.ok()).toBe(true);
  expect(await csv.text()).toContain("publisher_transcript");
  await page.screenshot({ path: testInfo.outputPath("mobile.png"), fullPage: true });
});
