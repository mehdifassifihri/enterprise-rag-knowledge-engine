import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
async function files(root) {
  const entries = await readdir(root, { withFileTypes: true });
  const groups = await Promise.all(
    entries.map((e) =>
      e.isDirectory()
        ? files(path.join(root, e.name))
        : [path.join(root, e.name)],
    ),
  );
  return groups.flat();
}
const assets = (await files(".next/static")).filter((f) => f.endsWith(".js"));
const values = [
  process.env.BACKEND_API_KEY,
  process.env.SESSION_SECRET,
  process.env.DEMO_PASSWORD,
].filter((v) => v && v.length >= 16 && !v.startsWith("REPLACE_"));
for (const file of assets) {
  const source = await readFile(file, "utf8");
  if (
    /BACKEND_API_KEY|SESSION_SECRET|DEMO_PASSWORD/.test(source) ||
    values.some((v) => source.includes(v))
  )
    throw new Error(
      `Server-only credential reference found in client asset: ${file}`,
    );
}
console.log(
  `Passed client-boundary scan across ${assets.length} JavaScript assets. This is not a comprehensive secret audit.`,
);
