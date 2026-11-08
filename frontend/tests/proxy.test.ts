import { afterEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "../src/app/api/bff/[...path]/route";
import { issueSession } from "../src/lib/session";
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
function headers() {
  vi.stubEnv(
    "SESSION_SECRET",
    "test-only-session-secret-with-at-least-32-characters",
  );
  vi.stubEnv("BACKEND_API_KEY", "test-only-tenant-key-32-characters-long");
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8000");
  vi.stubEnv("APP_ORIGIN", "http://localhost:3000");
  return {
    cookie: `eke_demo_session=${issueSession()}`,
    origin: "http://localhost:3000",
  };
}
it("does not act as an unauthenticated credential proxy", async () => {
  const r = await GET(
    new NextRequest("http://localhost:3000/api/bff/documents"),
    { params: Promise.resolve({ path: ["documents"] }) },
  );
  expect(r.status).toBe(401);
});
it("rejects unknown upstream paths", async () => {
  const r = await GET(
    new NextRequest("http://localhost:3000/api/bff/admin", {
      headers: headers(),
    }),
    { params: Promise.resolve({ path: ["admin"] }) },
  );
  expect(r.status).toBe(404);
});
it("does not forward browser tenant fields", async () => {
  const mocked = vi.fn();
  vi.stubGlobal("fetch", mocked);
  const r = await POST(
    new NextRequest("http://localhost:3000/api/bff/search", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        query: "refund",
        mode: "hybrid",
        top_k: 5,
        rerank: false,
        tenant_id: "forged",
      }),
    }),
    { params: Promise.resolve({ path: ["search"] }) },
  );
  expect(r.status).toBe(422);
  expect(mocked).not.toHaveBeenCalled();
});
it("uses only the configured server credential upstream", async () => {
  const mocked = vi
    .fn()
    .mockResolvedValue(Response.json({ items: [], limit: 20, offset: 0 }));
  vi.stubGlobal("fetch", mocked);
  const r = await GET(
    new NextRequest("http://localhost:3000/api/bff/documents", {
      headers: { ...headers(), "X-API-Key": "attacker" },
    }),
    { params: Promise.resolve({ path: ["documents"] }) },
  );
  expect(r.status).toBe(200);
  expect(mocked.mock.calls[0][1].headers["X-API-Key"]).toBe(
    "test-only-tenant-key-32-characters-long",
  );
  expect(r.headers.get("cache-control")).toContain("no-store");
});
it("distinguishes malformed upstream output from invalid caller JSON", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("<html>upstream error</html>", { status: 200 }),
      ),
  );
  const r = await GET(
    new NextRequest("http://localhost:3000/api/bff/documents", {
      headers: headers(),
    }),
    { params: Promise.resolve({ path: ["documents"] }) },
  );
  expect(r.status).toBe(502);
});
it("reports upstream timeouts without exception contents", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockRejectedValue(
        new DOMException("private upstream detail", "TimeoutError"),
      ),
  );
  const r = await GET(
    new NextRequest("http://localhost:3000/api/bff/documents", {
      headers: headers(),
    }),
    { params: Promise.resolve({ path: ["documents"] }) },
  );
  expect(r.status).toBe(504);
  expect(await r.text()).not.toContain("private upstream detail");
});

it("exposes an allowlisted QA category without private error content", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      Response.json(
        {
          status: "error",
          question: "PRIVATE QUESTION",
          answer: "PRIVATE ANSWER",
          error: {
            code: "invalid_citation",
            message: "PRIVATE PROVIDER DETAILS",
          },
        },
        { status: 502, headers: { "x-request-id": "trace-123" } },
      ),
    ),
  );
  const r = await POST(
    new NextRequest("http://localhost:3000/api/bff/ask", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ question: "policy" }),
    }),
    { params: Promise.resolve({ path: ["ask"] }) },
  );
  expect(r.status).toBe(502);
  const body = await r.json();
  expect(body.code).toBe("invalid_citation");
  expect(body.request_id).toBe("trace-123");
  expect(JSON.stringify(body)).not.toContain("PRIVATE");
});

it("does not relay unknown provider errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      Response.json(
        {
          error: { code: "PRIVATE", message: "PRIVATE" },
        },
        { status: 502 },
      ),
    ),
  );
  const r = await POST(
    new NextRequest("http://localhost:3000/api/bff/ask", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ question: "policy" }),
    }),
    { params: Promise.resolve({ path: ["ask"] }) },
  );
  expect(await r.text()).not.toContain("PRIVATE");
});
