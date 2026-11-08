import { NextRequest, NextResponse } from "next/server";
import {
  authorized,
  COOKIE,
  issueSession,
  passwordMatches,
  sameOrigin,
} from "@/lib/session";
import { boundedBody } from "@/lib/body";
export const runtime = "nodejs";
export async function GET(request: NextRequest) {
  return NextResponse.json(
    { authenticated: authorized(request) },
    { headers: { "Cache-Control": "no-store" } },
  );
}
export async function POST(request: NextRequest) {
  if (!sameOrigin(request))
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  if (Number(request.headers.get("content-length")) > 2048)
    return NextResponse.json({ error: "Input too large" }, { status: 413 });
  try {
    const raw = new TextDecoder().decode(await boundedBody(request, 2048));
    if (raw.length > 2048)
      return NextResponse.json({ error: "Input too large" }, { status: 413 });
    const { password } = JSON.parse(raw);
    if (
      typeof password !== "string" ||
      password.length > 256 ||
      !passwordMatches(password)
    )
      return NextResponse.json(
        { error: "Invalid demo password" },
        { status: 401 },
      );
    const response = NextResponse.json({ authenticated: true });
    response.cookies.set(COOKIE, issueSession(), {
      httpOnly: true,
      secure: process.env.APP_ORIGIN?.startsWith("https://") ?? false,
      sameSite: "strict",
      path: "/",
      maxAge: 28800,
    });
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch (error) {
    if (error instanceof SyntaxError)
      return NextResponse.json({ error: "Invalid request" }, { status: 422 });
    if (error instanceof Error && error.message === "body_limit")
      return NextResponse.json({ error: "Input too large" }, { status: 413 });
    return NextResponse.json(
      { error: "Demo login is unavailable" },
      { status: 503 },
    );
  }
}
export async function DELETE(request: NextRequest) {
  if (!sameOrigin(request))
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set(COOKIE, "", {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });
  return response;
}
