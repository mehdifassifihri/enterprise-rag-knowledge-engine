import { cp } from "node:fs/promises";
// Next's standalone artifact intentionally excludes public/static assets.
await cp(".next/static", ".next/standalone/.next/static", { recursive: true });
await cp("public", ".next/standalone/public", { recursive: true });
process.env.HOSTNAME ||= "127.0.0.1";
await import("../.next/standalone/server.js");
