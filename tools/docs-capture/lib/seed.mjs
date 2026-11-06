/**
 * Start an isolated Kontext stack for documentation capture.
 *
 * Two processes, mirroring `pnpm run dev:local`:
 *
 *   - the local API on `apiPort`
 *   - the Vite dev server on `appPort`
 *
 * The dev server is used instead of the packaged `app/dist` because
 * `kontext-labs serve` mounts `/assets` and `/static` but not `/icons`, so the
 * header logo and favicons 404 when the built app is served by the Python
 * process. Vite serves `app/public` at the root, which is what users see behind
 * nginx in a release.
 *
 * Isolation matters: the API would otherwise read and write the developer's real
 * `~/.kontext` database. Everything lives under a temporary directory that is
 * removed on exit.
 */
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

import { repoRoot } from "./paths.mjs";

const SETUP_PROFILE = {
   firstName: "Raymond",
   lastName: "Tang",
   email: "raymond.tang@example.com"
};

const FIXED_JWT_SECRET = "kontext-docs-capture-fixed-secret";
const STARTUP_TIMEOUT_MS = 120_000;

function delay(ms) {
   return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url, init) {
   const response = await fetch(url, init);
   const text = await response.text();
   let body = null;
   try {
      body = text ? JSON.parse(text) : null;
   } catch {
      body = text;
   }
   return { status: response.status, body };
}

async function waitForHttp(url, { timeout = STARTUP_TIMEOUT_MS, label, process }) {
   const deadline = Date.now() + timeout;
   let lastError = null;
   while (Date.now() < deadline) {
      if (process && process.child.exitCode !== null) {
         throw new Error(
            `${label} exited during startup (code ${process.child.exitCode}).\n` +
               tail(process.logFile)
         );
      }
      try {
         const response = await fetch(url);
         if (response.ok) return;
         lastError = new Error(`${url} returned ${response.status}`);
      } catch (error) {
         lastError = error;
      }
      await delay(250);
   }
   throw new Error(`Timed out waiting for ${label} at ${url}: ${lastError?.message ?? ""}`);
}

function isPortFree(port) {
   return new Promise((resolve) => {
      const server = net.createServer();
      server.once("error", () => resolve(false));
      server.once("listening", () => server.close(() => resolve(true)));
      server.listen(port, "127.0.0.1");
   });
}

async function pickPort(candidates, label) {
   for (const port of candidates) {
      if (await isPortFree(port)) return port;
   }
   throw new Error(
      `No free ${label} port among ${candidates.join(", ")}. ` +
         "Stop the process using them (often a running `pnpm run dev:local`) and retry."
   );
}

function spawnLogged({ name, command, args, env, logFile, cwd }) {
   const logFd = fs.openSync(logFile, "a");
   const child = spawn(command, args, {
      cwd,
      env,
      detached: true,
      stdio: ["ignore", logFd, logFd]
   });
   child.on("exit", () => {});
   return { name, child, logFd, logFile };
}

async function stopProcesses(processes) {
   for (const process of processes) {
      if (process.child.exitCode !== null) continue;
      try {
         process.kill(-process.child.pid, "SIGTERM");
      } catch {
         process.child.kill("SIGTERM");
      }
   }

   const deadline = Date.now() + 8_000;
   while (Date.now() < deadline) {
      const alive = processes.filter((process) => process.child.exitCode === null);
      if (alive.length === 0) break;
      await delay(100);
   }

   for (const process of processes) {
      if (process.child.exitCode === null) {
         try {
            process.kill(-process.child.pid, "SIGKILL");
         } catch {
            process.child.kill("SIGKILL");
         }
      }
      try {
         fs.closeSync(process.logFd);
      } catch {
         // Already closed.
      }
   }
}

function tail(file, lines = 40) {
   if (!fs.existsSync(file)) return "(no log)";
   return fs.readFileSync(file, "utf8").split("\n").slice(-lines).join("\n");
}

export async function startServer({ apiPort, appPort } = {}) {
   const resolvedApiPort = apiPort ?? (await pickPort([8101, 8102, 8103], "API"));
   // Only ports in LOCAL_CORS_ORIGINS can be used for the app, otherwise the
   // browser blocks the config and API calls.
   const resolvedAppPort = appPort ?? (await pickPort([8006, 8003], "app"));

   const runDir = fs.mkdtempSync(path.join(os.tmpdir(), "kontext-docs-"));
   const lakeDir = path.join(runDir, "lake");
   const fakeHome = path.join(runDir, "home");
   // The worker calls `configure_local_runtime`, which overwrites
   // `PROJECT_DB_URL` with `<HOME>/.kontext/kontext.db`. Keep the API and the
   // worker on one database by making that the same file the API is given;
   // otherwise the worker polls an empty database and jobs stay queued.
   const dbFile = path.join(fakeHome, ".kontext", "kontext.db");
   const apiLog = path.join(runDir, "api.log");
   const appLog = path.join(runDir, "app.log");
   const workerLog = path.join(runDir, "worker.log");

   fs.mkdirSync(path.dirname(dbFile), { recursive: true });

   async function readLaunchToken() {
      const tokenFile = path.join(fakeHome, ".kontext", "runtime", "launch.token");
      const deadline = Date.now() + 30_000;
      while (Date.now() < deadline) {
         try {
            const token = fs.readFileSync(tokenFile, "utf8").trim();
            if (token) return token;
         } catch {
            // The API writes it during startup.
         }
         await delay(200);
      }
      throw new Error(`Local launch token was not written to ${tokenFile}`);
   }

   // `kontext-labs serve` resolves the local data directory from `Path.home()`
   // (profiles, project storage, the internal lakehouse). `KONTEXT_LAKE_PATH`
   // alone is not enough: uploads otherwise land in the developer's real
   // `~/.kontext`. Give the API process a throwaway HOME, and point uv at the
   // real cache so it does not re-download wheels.
   const uvCacheDir =
      process.env.UV_CACHE_DIR ?? path.join(os.homedir(), ".cache", "uv");

   const apiUrl = `http://127.0.0.1:${resolvedApiPort}`;
   const appUrl = `http://localhost:${resolvedAppPort}`;

   const sharedEnv = {
      ...process.env,
      KONTEXT_LAKE_PATH: lakeDir,
      KONTEXT_JWT_SECRET_KEY: FIXED_JWT_SECRET,
      KONTEXT_LOCAL_MODE: "true",
      KONTEXT_LOG_LEVEL: "warning",
      STORAGE_PROVIDER: "local"
   };

   const api = spawnLogged({
      name: "api",
      command: "uv",
      args: [
         "run",
         "--package",
         "kontext-labs",
         "kontext-labs",
         "serve",
         "--host",
         "127.0.0.1",
         "--port",
         String(resolvedApiPort),
         "--no-worker",
         "--lake-path",
         lakeDir
      ],
      env: {
         ...sharedEnv,
         HOME: fakeHome,
         USERPROFILE: fakeHome,
         UV_CACHE_DIR: uvCacheDir,
         PROJECT_DB_URL: `sqlite:///${dbFile}`,
         KONTEXT_LOCAL_WORKER_ENABLED: "false"
      },
      logFile: apiLog,
      cwd: repoRoot
   });

   const processes = [api];

   try {
      await waitForHttp(`${apiUrl}/health`, { label: "kontext-labs", process: api });
      const launchToken = await readLaunchToken();

      const app = spawnLogged({
         name: "app",
         command: "pnpm",
         args: [
            "--filter",
            "@kontext-labs/app",
            "dev",
            "--",
            "--port",
            String(resolvedAppPort),
            "--strictPort"
         ],
         env: {
            ...sharedEnv,
            BROWSER: "none",
            VITE_PORT: String(resolvedAppPort),
            PUBLIC_KONTEXT_API_URL: apiUrl,
            PUBLIC_KONTEXT_DATA_API_URL: apiUrl,
            PUBLIC_KONTEXT_URL: appUrl,
            PUBLIC_KONTEXT_APP_URL: appUrl
         },
         logFile: appLog,
         cwd: repoRoot
      });
      processes.push(app);

      await waitForHttp(appUrl, { label: "Vite dev server", process: app });
   } catch (error) {
      await stopProcesses(processes);
      throw new Error(
         `${error.message}\n\nAPI log:\n${tail(apiLog)}\n\nApp log:\n${tail(appLog)}`
      );
   }

   let workerProcess = null;

   async function startWorker() {
      if (workerProcess) return;
      workerProcess = spawnLogged({
         name: "worker",
         command: "uv",
         args: [
            "run",
            "--package",
            "kontext-labs",
            "python",
            "-m",
            "kontext.labs.local_worker"
         ],
         env: {
            ...sharedEnv,
            HOME: fakeHome,
            USERPROFILE: fakeHome,
            UV_CACHE_DIR: uvCacheDir,
            PROJECT_DB_URL: `sqlite:///${dbFile}`,
            KONTEXT_LOCAL_WORKER_ENABLED: "true"
         },
         logFile: workerLog,
         cwd: repoRoot
      });
      processes.push(workerProcess);
      // Give the supervisor time to import and start polling before callers
      // wait for the queue to drain.
      await delay(500);
   }

   async function stopWorker() {
      if (!workerProcess) return;
      const stopping = workerProcess;
      workerProcess = null;
      const index = processes.indexOf(stopping);
      if (index >= 0) processes.splice(index, 1);
      await stopProcesses([stopping]);
   }

   async function waitForIdleJobs({ timeout = 120_000 } = {}) {
      const deadline = Date.now() + timeout;
      while (Date.now() < deadline) {
         const count = execFileSync(
            "sqlite3",
            [
               dbFile,
               "select count(*) from job_runs where status in ('Queued','Dispatched','Running')"
            ],
            { encoding: "utf8" }
         ).trim();
         if (Number(count) === 0) return;
         await delay(500);
      }
      throw new Error(
         "Background jobs did not drain before the capture timeout. " +
            `See ${workerLog}.`
      );
   }

   async function setupStatus() {
      const { body } = await fetchJson(`${apiUrl}/setup/status`);
      return Boolean(body?.isSetupComplete);
   }

   const launchHeaders = () => ({ "x-kontext-launch-token": launchToken });

   async function getToken() {
      const { body } = await fetchJson(`${apiUrl}/host/auth/bootstrap`, {
         headers: launchHeaders()
      });
      return body?.accessToken?.accessToken ?? null;
   }

   async function completeSetup() {
      const response = await fetchJson(`${apiUrl}/setup`, {
         method: "POST",
         headers: { "content-type": "application/json", ...launchHeaders() },
         body: JSON.stringify(SETUP_PROFILE)
      });
      if (response.status !== 200) {
         throw new Error(
            `Local setup failed with ${response.status}: ${JSON.stringify(response.body)}`
         );
      }
      return response.body;
   }

   async function stop() {
      await stopProcesses(processes);
      if (process.env.DOCS_KEEP_RUN !== "1") {
         // The worker is in its own session and may still be flushing SQLite
         // files when the API exits, so removal can race with it briefly.
         try {
            fs.rmSync(runDir, {
               recursive: true,
               force: true,
               maxRetries: 20,
               retryDelay: 250
            });
         } catch (error) {
            console.warn(
               `[docs-capture] could not remove ${runDir}: ${error.code ?? error.message}`
            );
         }
      } else {
         console.log(`[docs-capture] kept run directory ${runDir}`);
      }
   }

   return {
      apiUrl,
      appUrl,
      baseUrl: appUrl,
      launchToken,
      runDir,
      dbFile,
      homeDir: fakeHome,
      completeSetup,
      getToken,
      setupStatus,
      startWorker,
      stopWorker,
      waitForIdleJobs,
      stop
   };
}
