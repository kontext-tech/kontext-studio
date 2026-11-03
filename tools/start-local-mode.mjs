import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// This file lives in `tools/`, one level below the workspace root. It used to
// be nested in `tools/dev/`, so keep this at a single `..` or the resolved root
// becomes the parent of the repository and every spawn fails with
// `spawn /bin/sh ENOENT` from the invalid cwd.
const workspaceRoot = path.resolve(__dirname, "..");
const envFile = path.join(workspaceRoot, ".env.local");

const uvCommand = process.platform === "win32" ? "uv.exe" : "uv";
const pnpmCommand = process.platform === "win32" ? "pnpm.cmd" : "pnpm";

const sharedLocalEnv = {
   ...process.env,
   STORAGE_PROVIDER: "local",
   KONTEXT_LOCAL_MODE: "true"
};

const childProcesses = [];
let shuttingDown = false;

function stopAll(signal = "SIGTERM") {
   if (shuttingDown) {
      return;
   }

   shuttingDown = true;

   for (const child of childProcesses) {
      if (!child.killed) {
         child.kill(signal);
      }
   }
}

function spawnService(name, command, args, options) {
   console.log(`[local-mode] starting ${name}`);

   const child = spawn(command, args, {
      cwd: workspaceRoot,
      stdio: "inherit",
      shell: process.platform !== "win32",
      ...options
   });

   childProcesses.push(child);

   child.on("exit", (code, signal) => {
      if (shuttingDown) {
         return;
      }

      const outcome =
         signal !== null ? `signal ${signal}` : `exit code ${code ?? 0}`;
      console.log(`[local-mode] ${name} stopped with ${outcome}`);
      stopAll();
      process.exit(code ?? 1);
   });

   child.on("error", (error) => {
      if (shuttingDown) {
         return;
      }

      console.error(`[local-mode] failed to start ${name}:`, error);
      stopAll();
      process.exit(1);
   });

   return child;
}

spawnService(
   "kontext-labs",
   uvCommand,
   [
      "run",
      "--env-file",
      envFile,
      "kontext-labs",
      "serve",
      "--reload",
      "--host",
      "0.0.0.0",
      "--port",
      "8000"
   ],
   {
      env: sharedLocalEnv
   }
);

spawnService("app", pnpmCommand, ["run", "dev"], {
   cwd: path.join(workspaceRoot, "app"),
   env: {
      ...sharedLocalEnv,
      VITE_PORT: "8002",
      BROWSER: "none",
      PUBLIC_KONTEXT_URL: "http://localhost:8002",
      PUBLIC_KONTEXT_API_URL: "http://localhost:8000",
      PUBLIC_KONTEXT_DATA_API_URL: "http://localhost:8000"
   }
});

const shutdownSignals = ["SIGINT", "SIGTERM", "SIGHUP"];

for (const signal of shutdownSignals) {
   process.on(signal, () => {
      stopAll(signal);
      process.exit(0);
   });
}
