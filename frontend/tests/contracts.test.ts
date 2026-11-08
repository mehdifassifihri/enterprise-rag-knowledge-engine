import { describe, expect, it } from "vitest";
import {
  askInputSchema,
  searchInputSchema,
  citationSchema,
} from "../src/lib/contracts";
import { errorMessage } from "../src/lib/api";
describe("backend-aligned request contracts", () => {
  it("rejects forged tenant identity and invalid retrieval limits", () => {
    expect(
      searchInputSchema.safeParse({
        query: "policy",
        mode: "hybrid",
        top_k: 51,
        rerank: false,
      }).success,
    ).toBe(false);
    expect(
      searchInputSchema.safeParse({
        query: "policy",
        mode: "hybrid",
        top_k: 5,
        rerank: false,
        tenant_id: "foreign",
      }).success,
    ).toBe(false);
  });
  it("bounds chat history independently of UI state", () => {
    expect(
      askInputSchema.safeParse({
        question: "policy",
        history: Array.from({ length: 5 }, () => ({
          role: "assistant",
          content: "x".repeat(1000),
        })),
      }).success,
    ).toBe(false);
  });
  it("requires actual citation identity and excerpts", () => {
    expect(
      citationSchema.safeParse({ source_id: "S1", filename: "invented.pdf" })
        .success,
    ).toBe(false);
  });
  it.each([401, 403, 404, 409, 413, 422, 429, 500, 502, 503, 504])(
    "has safe error feedback for %s",
    (status) => {
      expect(errorMessage(status).length).toBeGreaterThan(15);
    },
  );
});
