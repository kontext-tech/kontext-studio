import { spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
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

// Share one launch token with the API and print the app URL that carries it.
// Without the fragment the UI cannot bootstrap credentials from the local API.
const launchToken =
   process.env.KONTEXT_LOCAL_LAUNCH_TOKEN ||
   crypto.randomBytes(32).toString("base64url");
const appUrl = `http://localhost:8002/#token=${encodeURIComponent(launchToken)}`;
const runtimeDir = path.join(os.homedir(), ".kontext", "runtime");
const launchUrlFile = path.join(runtimeDir, "launch.url");
const launchPortUrlFile = path.join(runtimeDir, "launch-8002.url");
const tokenFile = path.join(runtimeDir, "launch.token");

const sharedLocalEnv = {
   ...process.env,
   STORAGE_PROVIDER: "local",
   KONTEXT_LOCAL_MODE: "true",
   KONTEXT_LOCAL_LAUNCH_TOKEN: launchToken
};

function writeLaunchUrl() {
   try {
      fs.mkdirSync(runtimeDir, { recursive: true, mode: 0o700 });
      for (const target of [launchUrlFile, launchPortUrlFile]) {
         fs.writeFileSync(target, `${appUrl}\n`, { mode: 0o600 });
         fs.chmodSync(target, 0o600);
      }
   } catch (error) {
      console.warn(
         `[local-mode] could not write ${launchUrlFile}:`,
         error instanceof Error ? error.message : error
      );
   }
}

function printLaunchBanner() {
   console.log(
      [
         "",
         "============================================================",
         `  Open Kontext: ${appUrl}`,
         `  Launch URL file: ${launchUrlFile}`,
         `  Token file: ${tokenFile}`,
         "============================================================",
         ""
      ].join("\n")
   );
}

async function announceWhenReady() {
   const deadline = Date.now() + 60_000;
   while (Date.now() < deadline) {
      try {
         const [api, ui] = await Promise.all([
            fetch("http://127.0.0.1:8000/health"),
            fetch("http://127.0.0.1:8002/")
         ]);
         if (api.ok && ui.ok) {
            printLaunchBanner();
            return;
         }
      } catch {
         // Services are still starting.
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
   }
}

writeLaunchUrl();
printLaunchBanner();

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

// Print the banner again once both services answer, after the noisy startup
// logs, so the launch URL is the last thing in the terminal.
void announceWhenReady();

const shutdownSignals = ["SIGINT", "SIGTERM", "SIGHUP"];

for (const signal of shutdownSignals) {
   process.on(signal, () => {
      stopAll(signal);
      process.exit(0);
   });
}
