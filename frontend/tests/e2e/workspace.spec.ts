import { test, expect } from "@playwright/test";
import path from "node:path";
test("real API workflow: upload, retrieval, cited answer, evaluation and deletion", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Demo password").fill(process.env.DEMO_PASSWORD!);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Knowledge overview" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Knowledge base", exact: true }).click();
  await page
    .getByLabel("Upload document", { exact: true })
    .setInputFiles(path.resolve("../demo/sample_documents/returns.md"));
  await expect(page.getByText("returns.md is indexed and ready.")).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole("button", { name: "returns.md", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Stored chunks" }),
  ).toBeVisible();
  await expect(page.getByText("FACT:", { exact: false }).last()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("link", { name: "Retrieval playground", exact: true })
    .click();
  await page.getByLabel("Search query").fill("retail returns");
  await page
    .getByRole("button", { name: "Search knowledge", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "1 retrieved passages" }),
  ).toBeVisible();
  await expect(page.getByText("rrf ·", { exact: false })).toBeVisible();
  await page.getByRole("link", { name: "AI assistant", exact: true }).click();
  await page
    .getByLabel("Ask a question", { exact: true })
    .fill("What is the retail returns policy?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByRole("button", { name: "View source S1:", exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "View source S1:", exact: false })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Source details" }),
  ).toContainText("returns.md");
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    animations: "disabled",
    path: "test-results/assistant-desktop.png",
    fullPage: true,
  });
  await page
    .getByLabel("Ask a question", { exact: true })
    .fill("What is the executive bonus amount?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByText("Insufficient evidence", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Evaluation lab", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Quality across retrieval cutoffs" }),
  ).toBeVisible();
  await expect(page.getByText("0.1667", { exact: true }).first()).toBeVisible();
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    animations: "disabled",
    path: "test-results/evaluation-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "1 of 1 documents ready" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Knowledge overview" }),
  ).toBeVisible();
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    animations: "disabled",
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Knowledge overview" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    animations: "disabled",
    path: "test-results/dashboard-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Knowledge base", exact: true })
    .click();
  await page.getByRole("button", { name: "Delete returns.md" }).click();
  await page
    .getByRole("button", { name: "Delete document", exact: true })
    .click();
  await expect(
    page.getByText("No documents here yet", { exact: true }),
  ).toBeVisible();
});
test("BFF protects data and the client bundle contains no configured backend credential", async ({
  request,
}) => {
  expect((await request.get("/api/bff/documents")).status()).toBe(401);
  const login = await request.post("/api/session", {
    headers: { origin: process.env.E2E_BASE_URL || "http://localhost:3008" },
    data: { password: process.env.DEMO_PASSWORD },
  });
  expect(login.ok()).toBe(true);
  expect(
    (
      await request.post("/api/bff/search", {
        headers: { origin: "https://attacker.example" },
        data: { query: "retail", mode: "keyword", top_k: 5, rerank: false },
      })
    ).status(),
  ).toBe(403);
  const result = await request.get("/api/bff/evaluation");
  expect(result.ok()).toBe(true);
  expect((await result.text()).includes(process.env.BACKEND_API_KEY!)).toBe(
    false,
  );
});

test("responsive pages, dark mode and keyboard-accessible mobile navigation", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Demo password").fill(process.env.DEMO_PASSWORD!);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Knowledge overview" }),
  ).toBeVisible();
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of [
      "dashboard",
      "knowledge",
      "assistant",
      "playground",
      "evaluation",
      "settings",
    ]) {
      await page.goto(`/${route}`);
      await expect(page.locator("main#main h1")).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
        )
        .toBe(true);
      await page.screenshot({
        animations: "disabled",
        path: `test-results/${route}-${width}.png`,
        fullPage: true,
      });
    }
  }
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Knowledge overview" }),
  ).toBeVisible();
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    animations: "disabled",
    path: "test-results/dashboard-dark.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open navigation" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeFocused();
});

test("workspace page finder supports keyboard, filtering and navigation", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Demo password").fill(process.env.DEMO_PASSWORD!);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Knowledge overview" }),
  ).toBeVisible();
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Go to your workspace" });
  await expect(dialog).toBeVisible();
  await page.getByLabel("Find a workspace page").fill("does-not-exist");
  await expect(
    dialog.getByText("No matching pages.", { exact: false }),
  ).toBeVisible();
  await page.getByLabel("Find a workspace page").fill("retrieval");
  await expect(dialog.getByRole("link")).toHaveCount(1);
  await dialog.getByRole("link", { name: "Retrieval playground" }).click();
  await expect(
    page.getByRole("heading", { name: "Retrieval playground", exact: true }),
  ).toBeVisible();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("button", { name: "Search workspace navigation" })
    .click();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Search workspace navigation" }),
  ).toBeFocused();
});

test("focused chat supports suggestions, context controls, sources and a clean new conversation", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Demo password").fill(process.env.DEMO_PASSWORD!);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Knowledge overview" }),
  ).toBeVisible();
  await page.goto("/assistant");
  await expect(
    page.getByRole("heading", { name: "AI knowledge assistant", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Send question" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Refund policy", exact: true })
    .click();
  await expect(page.getByLabel("Ask a question", { exact: true })).toHaveValue(
    "What is the customer refund policy?",
  );
  await expect(
    page.getByLabel("Ask a question", { exact: true }),
  ).toBeFocused();
  await expect(
    page.getByRole("button", { name: "Send question" }),
  ).toBeEnabled();
  const context = page.getByRole("checkbox", { name: "Conversation context" });
  await expect(context).toBeChecked();
  await context.uncheck();
  await expect(context).not.toBeChecked();
  await page.getByRole("button", { name: "Show source panel" }).click();
  await expect(
    page.getByRole("complementary", { name: "Source details" }),
  ).toContainText("Evidence lives here");
  await page.getByRole("button", { name: "Hide source panel" }).click();
  await expect(
    page.getByRole("complementary", { name: "Source details" }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByLabel("Ask a question", { exact: true })).toHaveValue(
    "",
  );
  await expect(
    page.getByRole("button", { name: "Send question" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("link", { name: "Add documents", exact: true }),
  ).toHaveAttribute("href", "/knowledge");
});
