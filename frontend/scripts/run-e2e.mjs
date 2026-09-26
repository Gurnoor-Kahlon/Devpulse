import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { once } from "node:events";
import { setTimeout as delay } from "node:timers/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontend = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const backend = path.resolve(frontend, "../backend");
const python = path.join(
  path.resolve(backend, ".."),
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const env = {
  ...Object.fromEntries(
    Object.entries(process.env).filter(([key]) => !key.startsWith("DEVPULSE_")),
  ),
  PLAYWRIGHT_BROWSERS_PATH: path.resolve(frontend, "../.cache/playwright"),
};
if (!env.TEST_DATABASE_URL)
  throw new Error(
    "Set TEST_DATABASE_URL to a dedicated PostgreSQL _test database.",
  );

async function freePort(port) {
  const probe = createServer();
  probe.listen(port, "127.0.0.1");
  await once(probe, "listening");
  await new Promise((resolve) => probe.close(resolve));
}
async function ready(url, process) {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (process.exitCode !== null)
      throw new Error("Test server exited during startup.");
    try {
      if ((await fetch(url, { signal: AbortSignal.timeout(1000) })).ok) return;
    } catch {
      /* Not listening yet. */
    }
    await delay(500);
  }
  throw new Error("Test server did not become ready.");
}
await freePort(8000);
await freePort(3000);
let api, web, browser;
try {
  api = spawn(python, ["-m", "tests.e2e_server"], {
    cwd: backend,
    env,
    stdio: ["pipe", "inherit", "inherit"],
  });
  await ready("http://127.0.0.1:8000/health/ready", api);
  web = spawn(
    process.execPath,
    ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1"],
    { cwd: frontend, env, stdio: "inherit" },
  );
  await ready("http://localhost:3000/login", web);
  browser = spawn(
    process.execPath,
    ["node_modules/@playwright/test/cli.js", "test", ...process.argv.slice(2)],
    { cwd: frontend, env, stdio: "inherit" },
  );
  const [code] = await once(browser, "exit");
  process.exitCode = code ?? 1;
} finally {
  if (browser && browser.exitCode === null) browser.kill();
  if (web && web.exitCode === null) {
    web.kill();
    await once(web, "exit");
  }
  if (api && api.exitCode === null) {
    // Graceful stdin shutdown also works on Windows, so the temporary schema is dropped.
    api.stdin.end("stop\n");
    const timer = setTimeout(() => api.kill(), 10_000);
    await once(api, "exit");
    clearTimeout(timer);
  }
}
