#!/usr/bin/env bun
// Runs the read-only Python CLI from the repository root. No install dependencies.
import { resolve } from "node:path";
const root = resolve(import.meta.dir, "../../../../..");
const binary = process.platform === "win32" ? "python" : "python3";
const child = Bun.spawnSync([binary, "-m", "uk_hunter", ...process.argv.slice(2)], {
  cwd: root,
  stdin: "ignore",
  stdout: "inherit",
  stderr: "inherit",
});
if (child.error) {
  console.error(JSON.stringify({ error: String(child.error), code: "PYTHON_UNAVAILABLE" }));
  process.exit(1);
}
process.exit(child.exitCode ?? 1);
