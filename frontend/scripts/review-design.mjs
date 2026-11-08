// Read-only visual review of an operator-selected running workspace.
// Password is supplied to this process only; never written to screenshots or output.
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
const origin = process.env.REVIEW_ORIGIN || "http://localhost:3000";
const output = process.env.REVIEW_OUTPUT || "/tmp/eke-redesign";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1080 },
  });
  await page.goto(`${origin}/login`);
  await page.screenshot({
    animations: "disabled",
    path: `${output}/login.png`,
    fullPage: true,
  });
  await page.getByLabel("Demo password").fill(process.env.DEMO_PASSWORD);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("heading", { name: "Knowledge overview" }).waitFor();
  for (const width of process.env.REVIEW_MOBILE_ONLY
    ? [390]
    : [1440, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 });
    for (const route of [
      "dashboard",
      "knowledge",
      "assistant",
      "playground",
      "evaluation",
      "settings",
    ]) {
      await page.goto(`${origin}/${route}`);
      await page.locator("#main h1").waitFor();
      await page.waitForTimeout(600);
      if (
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        )
      ) {
        await page.screenshot({
          animations: "disabled",
          path: `${output}/overflow-${route}-${width}.png`,
          fullPage: true,
        });
        console.log(
          await page.evaluate(() =>
            [...document.querySelectorAll("body *")]
              .map((el) => ({
                tag: el.tagName,
                class: el.className,
                left: el.getBoundingClientRect().left,
                right: el.getBoundingClientRect().right,
              }))
              .filter(
                (el) =>
                  el.right > innerWidth + 1 && typeof el.class === "string",
              )
              .slice(0, 20),
          ),
        );
        throw new Error(`Horizontal overflow: ${route} at ${width}`);
      }
      await page.screenshot({
        animations: "disabled",
        path: `${output}/${route}-${width}.png`,
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto(`${origin}/dashboard`);
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await page.waitForTimeout(400);
  await page.screenshot({
    animations: "disabled",
    path: `${output}/dashboard-dark.png`,
    fullPage: true,
  });
  console.log(
    "Reviewed all six pages at the selected viewport sizes without horizontal overflow; screenshots saved.",
  );
} finally {
  await browser.close();
}
