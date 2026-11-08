import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import {
  authorized,
  issueSession,
  passwordMatches,
  sameOrigin,
} from "../src/lib/session";
import { POST } from "../src/app/api/session/route";
afterEach(() => vi.unstubAllEnvs());
function configure() {
  vi.stubEnv("SESSION_SECRET", "test-only-session-secret-with-32-characters");
  vi.stubEnv("DEMO_PASSWORD", "test-only-demo-password");
  vi.stubEnv("APP_ORIGIN", "http://localhost:3000");
}
describe("server-side demo authentication", () => {
  it("fails closed without configuration", () => {
    expect(authorized(new NextRequest("http://localhost:3000"))).toBe(false);
  });
  it("validates signed cookies and rejects tampering", () => {
    configure();
    const session = issueSession();
    expect(
      authorized(
        new NextRequest("http://localhost:3000", {
          headers: { cookie: `eke_demo_session=${session}` },
        }),
      ),
    ).toBe(true);
    expect(
      authorized(
        new NextRequest("http://localhost:3000", {
          headers: { cookie: `eke_demo_session=${session}X` },
        }),
      ),
    ).toBe(false);
  });
  it("does not accept a cross-origin write", async () => {
    configure();
    const request = new NextRequest("http://localhost:3000/api/session", {
      method: "POST",
      headers: { origin: "https://attacker.example" },
      body: "{}",
    });
    expect(sameOrigin(request)).toBe(false);
    expect((await POST(request)).status).toBe(403);
  });
  it("checks passwords without exposing backend credentials", () => {
    configure();
    expect(passwordMatches("wrong-password")).toBe(false);
    expect(passwordMatches("test-only-demo-password")).toBe(true);
  });
});
