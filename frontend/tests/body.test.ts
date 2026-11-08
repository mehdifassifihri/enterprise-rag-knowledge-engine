import { expect, it } from "vitest";
import { boundedBody } from "../src/lib/body";
it("caps actual streamed bytes even without Content-Length", async () => {
  const request = new Request("http://localhost", {
    method: "POST",
    body: "x".repeat(1025),
  });
  await expect(boundedBody(request, 1024)).rejects.toThrow("body_limit");
});
it("preserves allowed request bytes", async () => {
  const body = await boundedBody(
    new Request("http://localhost", { method: "POST", body: "synthetic" }),
    100,
  );
  expect(new TextDecoder().decode(body)).toBe("synthetic");
});
