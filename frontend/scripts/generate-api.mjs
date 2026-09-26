import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
import { format } from "prettier";

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
const schema = execFileSync(
  python,
  [
    "-c",
    "import json; from app.factory import create_app; from app.core.config import Settings; print(json.dumps(create_app(Settings(_env_file=None, environment='test')).openapi()))",
  ],
  {
    cwd: backend,
    encoding: "utf8",
    maxBuffer: 5 * 1024 * 1024,
    env: Object.fromEntries(
      Object.entries(process.env).filter(
        ([key]) => !key.startsWith("DEVPULSE_"),
      ),
    ),
  },
);
const source = astToString(await openapiTS(JSON.parse(schema)));
const output = await format(
  `// Generated from FastAPI OpenAPI. Run npm run api:generate; do not edit.\n${source}`,
  { parser: "typescript" },
);
const destination = path.join(frontend, "src/lib/api/schema.d.ts");
if (process.argv.includes("--check")) {
  if ((await readFile(destination, "utf8")) !== output)
    throw new Error("API types are stale. Run npm run api:generate.");
  console.log("API types match FastAPI.");
} else {
  await writeFile(destination, output);
  console.log("API types generated from FastAPI.");
}
