import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { serviceErrors } from "@/lib/service-errors";
import { boundedBody } from "@/lib/body";
import { authorized, sameOrigin } from "@/lib/session";
import { readEvaluation } from "@/lib/evaluation";
import { askInputSchema, searchInputSchema } from "@/lib/contracts";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const id = z.string().uuid();
const json = (body: unknown, status = 200) =>
  NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "private, no-store" },
  });
async function handler(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  if (!authorized(request))
    return json({ error: "Authentication required" }, 401);
  if (request.method !== "GET" && !sameOrigin(request))
    return json({ error: "Forbidden origin" }, 403);
  const { path } = await context.params;
  const route = path.join("/");
  if (route === "evaluation" && request.method === "GET")
    return json(await readEvaluation());
  const documentPath =
    path.length === 2 &&
    path[0] === "documents" &&
    id.safeParse(path[1]).success;
  const chunksPath =
    path.length === 3 &&
    path[0] === "documents" &&
    id.safeParse(path[1]).success &&
    path[2] === "chunks";
  const read =
    [
      "health",
      "ready",
      "info",
      "capabilities",
      "documents",
      "documents/stats",
    ].includes(route) ||
    documentPath ||
    chunksPath;
  if (!(
    (request.method === "GET" && read) ||
    (request.method === "DELETE" && documentPath) ||
    (request.method === "POST" &&
      ["search", "ask", "documents/upload"].includes(route))
  ))
    return json({ error: "Route unavailable" }, 404);
  const base = process.env.BACKEND_URL;
  const key = process.env.BACKEND_API_KEY;
  if (!base || !key || key.startsWith("REPLACE_"))
    return json({ error: "Backend connection not configured" }, 503);
  try {
    const url = new URL(
      (route === "health" || route === "ready" ? "/" : "/api/v1/") + route,
      base,
    );
    if (!["http:", "https:"].includes(url.protocol))
      return json({ error: "Invalid backend configuration" }, 503);
    // Never forward caller headers, credentials, tenant fields or arbitrary query parameters.
    for (const param of request.nextUrl.searchParams.keys())
      if (!["limit", "offset"].includes(param))
        return json({ error: "Invalid query parameter" }, 422);
    for (const param of ["limit", "offset"]) {
      const value = request.nextUrl.searchParams.get(param);
      if (value !== null) {
        const n = Number(value);
        if (
          !/^\d+$/.test(value) ||
          !Number.isInteger(n) ||
          n < 0 ||
          n > (param === "offset" ? 100000 : chunksPath ? 20 : 100) ||
          (param === "limit" && n === 0)
        )
          return json({ error: "Invalid pagination" }, 422);
        url.searchParams.set(param, value);
      }
    }
    const headers: Record<string, string> = { "X-API-Key": key };
    let body: BodyInit | undefined;
    if (request.method === "POST") {
      if (route === "documents/upload") {
        const type = request.headers.get("content-type") || "";
        if (!type.startsWith("multipart/form-data;"))
          return json({ error: "Multipart upload required" }, 422);
        headers["Content-Type"] = type;
        const bytes = await boundedBody(request, 11 * 1024 * 1024);
        body = Buffer.from(bytes);
      } else {
        const bytes = await boundedBody(request, 12000);
        const input = JSON.parse(new TextDecoder().decode(bytes));
        const parsed = (
          route === "search" ? searchInputSchema : askInputSchema
        ).safeParse(input);
        if (!parsed.success) return json({ error: "Invalid request" }, 422);
        headers["Content-Type"] = "application/json";
        body = JSON.stringify(parsed.data);
      }
    }
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(
        route === "documents/upload" ? 175000 : 120000,
      ),
    });
    if (upstream.status === 204)
      return new Response(null, {
        status: 204,
        headers: { "Cache-Control": "no-store" },
      });
    if (!upstream.ok) {
      let code: string | undefined;
      if (route === "ask") {
        const failure = await upstream.json().catch(() => null);
        const candidate = failure?.error?.code;
        if (
          typeof candidate === "string" &&
          Object.hasOwn(serviceErrors, candidate)
        )
          code = candidate;
      }
      return json(
        {
          error: code ? serviceErrors[code] : "Backend request failed",
          code,
          status: upstream.status,
          request_id: upstream.headers.get("x-request-id"),
        },
        upstream.status,
      );
    }
    try {
      const data = await upstream.json();
      return json(data, upstream.status);
    } catch {
      return json({ error: "Invalid backend response" }, 502);
    }
  } catch (error) {
    if (error instanceof SyntaxError)
      return json({ error: "Invalid JSON" }, 422);
    if (error instanceof Error && error.message === "body_limit")
      return json({ error: "Request too large" }, 413);
    if (
      error instanceof Error &&
      ["TimeoutError", "AbortError"].includes(error.name)
    )
      return json({ error: "Backend timeout" }, 504);
    return json({ error: "Backend unavailable" }, 503);
  }
}
export const GET = handler;
export const POST = handler;
export const DELETE = handler;
