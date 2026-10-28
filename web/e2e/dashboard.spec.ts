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
  const manifest = await (await page.request.get("./figures/manifest.json")).json();
  expect(manifest.publication_status).toBe("local_only");
  expect(manifest.charts).toHaveLength(10);
  for (const chart of manifest.charts) {
    for (const format of ["png", "csv"]) {
      expect((await page.request.get(`./figures/${chart[format]}`)).ok()).toBe(true);
    }
  }
  const csv = await page.request.get("./data/ads.csv");
  expect(csv.ok()).toBe(true);
  expect(await csv.text()).toContain("publisher_transcript");
  await page.screenshot({ path: testInfo.outputPath("mobile.png"), fullPage: true });
  await page.goto("./article.html");
  await expect(page.getByText("DRAFT - NOT PUBLISHED.", { exact: true })).toBeVisible();
  await expect(page.locator("figure img")).toHaveCount(10);
  for (const image of await page.locator("figure img").all()) {
    await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate(node =>
      (node as HTMLImageElement).complete
      && (node as HTMLImageElement).naturalWidth > 0)).toBe(true);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("article-mobile.png"), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: testInfo.outputPath("article-desktop.png"), fullPage: true });
});

test("final-day defaults and single-message timeline have no future zeros or duplicate ticks", async ({ page }) => {
  const dataset = await (await page.request.get("./data/dataset.json")).json();
  const finalDay = {
    ...dataset, until: "2026-11-04", latest_release: "2026-11-04", examples: [],
    ads: [{ ...dataset.ads[0], alignment: "D", published: "2026-11-04",
      delivery_start: undefined, delivery_end: undefined }],
  };
  await page.route("**/data/dataset.json", route => route.fulfill({ json: finalDay }));
  await page.goto("./");
  await expect(page.getByRole("status")).toContainText("1 records");
  await expect(page.getByLabel("Released through")).toHaveValue("2026-11-04");
  const labels = await page.locator(".timeline .axis").allTextContents();
  expect(labels).toContain("Nov");
  expect(labels).not.toContain("Dec");
  expect(labels.filter(label => /^\d+$/.test(label))).toEqual(["0", "1"]);
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page.getByRole("status")).toContainText("1 records");
});

test("technical report keeps tables and expanded descriptor contexts inside mobile width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./report.html");
  await expect(page.getByRole("heading", { name: "The language of political ads", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const contexts = page.locator("details").filter({ hasText: "Read the extracted descriptor contexts" });
  await contexts.locator("summary").click();
  await expect(contexts).toHaveAttribute("open", "");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("unresolved alignment remains independently filterable with complete evidence", async ({ page }) => {
  await page.goto("./");
  const response = await page.request.get("./data/dataset.json");
  const dataset = await response.json();
  const included = dataset.ads.filter((ad: { alignment: string }) => ad.alignment === "unknown");
  expect(included.length).toBeGreaterThan(0);
  await page.getByLabel("Parties", { exact: true }).selectOption("unknown");
  await expect(page.getByRole("status")).toContainText(`${included.length} records`);
  const pendingDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download JSON" }).click();
  const stream = await (await pendingDownload).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk);
  const exported = JSON.parse(Buffer.concat(chunks).toString());
  expect(exported.ads).toEqual(included);
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page.getByRole("status")).toContainText(`${dataset.ads.length} records`);
});

test("reviewed bipartisan records display their basis and export unchanged evidence", async ({ page }) => {
  await page.goto("./");
  const response = await page.request.get("./data/dataset.json");
  const dataset = await response.json();
  const included = dataset.ads.filter((ad: { alignment: string }) => ad.alignment === "other");
  expect(included.length).toBeGreaterThan(0);
  expect(included.every((ad: { original_alignment: string; alignment_review: { status: string } }) =>
    ad.original_alignment === "unknown" && ad.alignment_review.status === "bipartisan")).toBe(true);
  await page.getByLabel("Parties", { exact: true }).selectOption("other");
  await expect(page.getByRole("status")).toContainText(`${included.length} records`);
  const card = page.locator(".ad-card").first();
  await card.getByRole("button", { name: "Read all available text" }).click();
  await expect(card.getByText("Reviewed publisher alignment", { exact: false })).toBeVisible();
  await expect(card.getByText("This supersedes the original alignment only.", { exact: false })).toBeVisible();
  await expect(card.getByRole("link", { name: "Alignment source 1", exact: true })).toBeVisible();
  const pendingDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download JSON" }).click();
  const stream = await (await pendingDownload).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk);
  expect(JSON.parse(Buffer.concat(chunks).toString()).ads).toEqual(included);
});
