import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
const output = "/tmp/eke-chat-review";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
  });
  await page.goto("http://localhost:3000/login");
  await page.getByLabel("Demo password").fill(process.env.DEMO_PASSWORD);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("heading", { name: "Knowledge overview" }).waitFor();
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.goto("http://localhost:3000/assistant");
    await page
      .getByRole("heading", { name: "AI knowledge assistant", exact: true })
      .waitFor();
    await page.waitForTimeout(400);
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw new Error(`Overflow at ${width}`);
    await page.screenshot({
      path: `${output}/welcome-${width}.png`,
      fullPage: true,
      animations: "disabled",
    });
  }
  await page
    .getByRole("button", { name: "Refund policy", exact: true })
    .click();
  if (
    !(
      await page.getByLabel("Ask a question", { exact: true }).inputValue()
    ).includes("refund")
  )
    throw new Error("Suggested question failed");
  await page.getByRole("button", { name: "Show source panel" }).click();
  await page.getByRole("complementary", { name: "Source details" }).waitFor();
  await page.getByRole("button", { name: "Hide source panel" }).click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await page.screenshot({
    path: `${output}/welcome-dark.png`,
    fullPage: true,
    animations: "disabled",
  });
  console.log(
    "Chat welcome, suggestions, source toggle, dark theme and three responsive widths passed; no model requests made.",
  );
} finally {
  await browser.close();
}
