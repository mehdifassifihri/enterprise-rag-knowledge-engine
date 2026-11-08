import "server-only";
import {
  createHmac,
  randomBytes,
  timingSafeEqual,
  createHash,
} from "node:crypto";
import type { NextRequest } from "next/server";
export const COOKIE = "eke_demo_session";
function secret() {
  const value = process.env.SESSION_SECRET;
  if (!value || value.length < 32 || value.startsWith("REPLACE_"))
    throw new Error("Demo session is not configured");
  return value;
}
function sign(value: string) {
  return createHmac("sha256", secret()).update(value).digest("base64url");
}
export function sameOrigin(request: Request) {
  const origin = request.headers.get("origin");
  const configured = process.env.APP_ORIGIN || "http://localhost:3000";
  return origin === new URL(configured).origin;
}
export function passwordMatches(value: string) {
  const expected = process.env.DEMO_PASSWORD;
  if (!expected || expected.length < 16 || expected.startsWith("REPLACE_"))
    throw new Error("Demo login is not configured");
  return timingSafeEqual(
    createHash("sha256").update(value).digest(),
    createHash("sha256").update(expected).digest(),
  );
}
export function issueSession() {
  const payload = `${Date.now() + 8 * 60 * 60 * 1000}.${randomBytes(24).toString("hex")}`;
  return `${payload}.${sign(payload)}`;
}
export function authorized(request: NextRequest) {
  try {
    const value = request.cookies.get(COOKIE)?.value;
    if (!value || value.length > 256) return false;
    const [expires, nonce, signature, ...extra] = value.split(".");
    if (
      extra.length ||
      !expires ||
      !nonce ||
      !signature ||
      !/^\d+$/.test(expires) ||
      !/^[a-f0-9]{48}$/.test(nonce)
    )
      return false;
    const expected = sign(`${expires}.${nonce}`);
    return (
      signature.length === expected.length &&
      timingSafeEqual(Buffer.from(signature), Buffer.from(expected)) &&
      Number(expires) > Date.now()
    );
  } catch {
    return false;
  }
}
