// Capture real UI/API states with public fixtures; called by demo_frontend.py.
import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";
const output = path.resolve("../docs/screenshots/rag-showcase");
const base = process.env.E2E_BASE_URL;
assert(
  base && process.env.DEMO_PASSWORD,
  "Run through scripts/demo_frontend.py --screenshots",
);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const captures = [];
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
    colorScheme: "light",
  });
  const page = await context.newPage();
  await page.goto(`${base}/login`);
  await page.getByLabel("Demo password").fill(process.env.DEMO_PASSWORD);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("heading", { name: "Knowledge overview" }).waitFor();
  async function capture(name) {
    await page.evaluate(() => {
      window.scrollTo(0, 0);
      if (document.activeElement instanceof HTMLElement)
        document.activeElement.blur();
    });
    await page.screenshot({
      path: path.join(output, `${name}.png`),
      animations: "disabled",
      fullPage: false,
    });
    captures.push(name);
    console.log(`Captured ${name}`);
  }
  async function ask(question) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/bff/ask") && r.request().method() === "POST",
    );
    await page.getByLabel("Ask a question", { exact: true }).fill(question);
    await page.getByRole("button", { name: "Send question" }).click();
    const r = await response;
    assert.equal(r.status(), 200, "QA response failed");
    return r.json();
  }
  await page.goto(`${base}/knowledge`);
  for (const name of ["returns.md", "portal.md", "device-service.md"]) {
    await page
      .getByLabel("Upload document", { exact: true })
      .setInputFiles(path.resolve(`../examples/qa/${name}`));
    await page
      .getByText(`${name} is indexed and ready.`, { exact: true })
      .waitFor();
  }
  assert.equal(
    (
      await (
        await context.request.get(`${base}/api/bff/documents/stats`)
      ).json()
    ).ready,
    3,
  );
  await page.getByRole("button", { name: "portal.md", exact: true }).waitFor();
  await capture("01-knowledge-base");
  await page.getByRole("button", { name: "returns.md", exact: true }).click();
  await page
    .getByRole("heading", { name: "Stored chunks", exact: true })
    .waitFor();
  await page.getByText("FACT:", { exact: false }).last().waitFor();
  await capture("02-source-chunks");
  await page.keyboard.press("Escape");
  await page.goto(`${base}/playground`);
  await page.getByLabel("Search query").fill("retail returns");
  const searchResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/bff/search") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Search knowledge", exact: true })
    .click();
  const retrieved = await (await searchResponse).json();
  assert.equal(retrieved.mode, "hybrid");
  assert(retrieved.results.length > 0);
  assert(
    retrieved.results.some(
      (r) => r.sources.includes("keyword") && r.sources.includes("vector"),
    ),
  );
  await page.getByText("rrf ·", { exact: false }).first().waitFor();
  await capture("03-hybrid-retrieval");
  await page.goto(`${base}/assistant`);
  const answer = await ask(
    "What is the retail returns policy and how do I submit the order information?",
  );
  assert.equal(answer.status, "answered");
  assert.equal(answer.citations.length, 2);
  for (const citation of answer.citations) {
    const chunks = await (
      await context.request.get(
        `${base}/api/bff/documents/${citation.document_id}/chunks?limit=20`,
      )
    ).json();
    const chunk = chunks.items.find((c) => c.id === citation.chunk_id);
    assert(
      chunk &&
        citation.supporting_quotes.every((quote) =>
          chunk.content.includes(quote),
        ),
      "Citation excerpt did not match stored chunk",
    );
  }
  const portal = answer.citations.find((c) => c.filename === "portal.md");
  await page
    .getByRole("button", {
      name: `View source ${portal.source_id}: portal.md`,
      exact: true,
    })
    .click();
  await page
    .getByRole("complementary", { name: "Source details" })
    .getByText("Submit the order number through the returns portal.", {
      exact: true,
    })
    .waitFor();
  await capture("04-grounded-answer");
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  const abstention = await ask("What is the executive bonus amount?");
  assert.equal(abstention.status, "insufficient_evidence");
  assert.equal(abstention.citations.length, 0);
  await page.getByText("Insufficient evidence", { exact: true }).waitFor();
  await capture("05-insufficient-evidence");
  await page.goto(`${base}/evaluation`);
  await page
    .getByRole("heading", { name: "Quality across retrieval cutoffs" })
    .waitFor();
  await page.getByText("0.1667", { exact: true }).first().waitFor();
  // Chart measurement settles after its ResizeObserver callback.
  await page.locator(".recharts-bar-rectangle").first().waitFor();
  await capture("06-evaluation");
  await writeFile(
    path.join(output, "manifest.json"),
    JSON.stringify(
      {
        captured_at: new Date().toISOString(),
        viewport: { width: 1440, height: 1100 },
        corpus: "examples/qa/*.md (three fictional public documents)",
        providers:
          "Deterministic DemoEmbeddings and DemoLLM; not real-model quality evidence",
        transport: "Chromium -> Next.js BFF -> FastAPI -> PostgreSQL/pgvector",
        answer_citations_verified_against_stored_chunks: 2,
        abstention_verified: true,
        captures,
      },
      null,
      2,
    ) + "\n",
  );
} finally {
  await browser.close();
}
