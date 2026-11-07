/**
 * Seed and assert the fixture workspace.
 *
 * Runs after `POST /setup` and before any `configured` story. The dataset is
 * Chinook: a real SQLite database plus CSV exports of the same tables, so every
 * screen in the guide tells one coherent story.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import {
   catalogEntities,
   catalogFixture,
   FIXTURE_EPOCH,
   FIXTURE_PROJECT_CODE,
   fixtureExpectations,
   knowledgeConcepts,
   seedFiles
} from "../fixtures.mjs";
import { CAPTURE_CLOCK } from "./browser.mjs";
import { repoRoot, toolsDir } from "./paths.mjs";

function qs(params) {
   const search = new URLSearchParams(params);
   return search.toString();
}

async function api(server, token, pathname, init = {}) {
   const response = await fetch(`${server.apiUrl}${pathname}`, {
      ...init,
      headers: {
         Authorization: `Bearer ${token}`,
         ...(init.body instanceof FormData
            ? {}
            : { "content-type": "application/json" }),
         ...init.headers
      }
   });
   const text = await response.text();
   let body = text;
   try {
      body = text ? JSON.parse(text) : null;
   } catch {
      // Non-JSON error payloads are kept as text for the thrown message.
   }
   if (!response.ok) {
      throw new Error(
         `Fixture request ${init.method ?? "GET"} ${pathname} failed with ${response.status}: ${text.slice(0, 400)}`
      );
   }
   return body;
}

function fixturePaths(server) {
   const root = path.join(server.homeDir, ".kontext", "storage", "fixtures");
   return {
      root,
      exports: path.join(root, "exports"),
      database: path.join(root, catalogFixture.databaseFile)
   };
}

/**
 * Build the Chinook database and its CSV exports inside the capture HOME.
 * One Python process keeps this fast and avoids shell quoting for the SQL.
 */
function prepareFixtureData(server) {
   const paths = fixturePaths(server);
   fs.mkdirSync(paths.exports, { recursive: true });
   fs.rmSync(paths.database, { force: true });
   for (const file of fs.readdirSync(paths.exports)) {
      fs.rmSync(path.join(paths.exports, file), { force: true });
   }

   const script = [
      "import csv, json, os, sqlite3",
      "connection = sqlite3.connect(os.environ['DOCS_DB'])",
      "with open(os.environ['DOCS_SQL'], encoding='utf-8') as handle:",
      "    connection.executescript(handle.read())",
      "connection.commit()",
      "for spec in json.loads(os.environ['DOCS_EXPORTS']):",
      "    cursor = connection.execute(spec['sql'])",
      "    target = os.path.join(os.environ['DOCS_EXPORT_DIR'], spec['name'])",
      "    with open(target, 'w', newline='', encoding='utf-8') as handle:",
      "        writer = csv.writer(handle)",
      "        writer.writerow([column[0] for column in cursor.description])",
      "        writer.writerows(cursor.fetchall())",
      "connection.close()"
   ].join("\n");

   execFileSync("uv", ["run", "--package", "kontext-studio", "python", "-"], {
      cwd: repoRoot,
      input: script,
      env: {
         ...process.env,
         DOCS_SQL: path.join(toolsDir, "fixtures", catalogFixture.sqlFile),
         DOCS_DB: paths.database,
         DOCS_EXPORT_DIR: paths.exports,
         DOCS_EXPORTS: JSON.stringify(
            seedFiles
               .filter((file) => file.sql)
               .map((file) => ({ name: file.name, sql: file.sql }))
         )
      },
      stdio: ["pipe", "ignore", "inherit"]
   });

   return paths;
}

export function stabilizeTimestamps(server) {
   const script = [
      "import datetime, json, os, sqlite3, time",
      "connection = sqlite3.connect(os.environ['DOCS_DB'])",
      "names = json.loads(os.environ['DOCS_NAMES'])",
      "epoch = int(os.environ['DOCS_EPOCH'])",
      "stamp = datetime.datetime.fromtimestamp(",
      "    epoch / 1000, datetime.UTC",
      ").strftime('%Y-%m-%d %H:%M:%S.%f')",
      "for index, name in enumerate(names):",
      "    value = datetime.datetime.fromtimestamp(",
      "        (epoch - index * 3600000) / 1000, datetime.UTC",
      "    ).strftime('%Y-%m-%d %H:%M:%S.%f')",
      "    connection.execute(",
      "        'UPDATE files SET date_created = ?, date_modified = ? WHERE name = ?',",
      "        [value, value, name],",
      "    )",
      "connection.commit()",
      "# A capture that starts the worker calls this function again after the",
      "# queue drains, so completed runs get stable start and end times.",
      "completed = (datetime.datetime.fromtimestamp(",
      "    epoch / 1000, datetime.UTC",
      ") + datetime.timedelta(seconds=60)).strftime('%Y-%m-%d %H:%M:%S.%f')",
      "actor = 'a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d'",
      "connection.execute(",
      "    'UPDATE jobs SET created_at = ?, updated_at = NULL, created_by = ?',",
      "    [stamp, f'User:{actor}'],",
      "    )",
      "connection.execute(",
      "    'UPDATE job_triggers SET created_at = ?, triggered_by_id = ?',",
      "    [stamp, actor],",
      "    )",
      "runs = connection.execute('select id from job_runs order by created_at, id').fetchall()",
      "for index, (run_id,) in enumerate(runs):",
      "    connection.execute(",
      "        'UPDATE job_runs SET created_at = ?, updated_at = ?, started_at = ?,'",
      "        ' completed_at = ?, execution_id = ?, worker = ?, status = ?, progress = ?,'",
      "        ' error_message = NULL WHERE id = ?',",
      "        [stamp, stamp, stamp, completed, f'202602161300{index:05d}', 'local-worker',",
      "         'Succeeded', 100, run_id],",
      "    )",
      "# Catalog syncs happen during seeding, so they carry the seeding wall",
      "# clock. Restamp them relative to the frozen page clock; otherwise the",
      "# Data Sources page renders them as a future time.",
      "sync = datetime.datetime.fromtimestamp(",
      "    int(os.environ['DOCS_SYNC_EPOCH']) / 1000, datetime.UTC",
      ").strftime('%Y-%m-%d %H:%M:%S.%f')",
      "connection.execute(",
      "    'UPDATE catalog_connections SET last_synced_at = ?, created_at = ?, updated_at = ?'",
      "    ' WHERE last_synced_at IS NOT NULL',",
      "    [sync, sync, sync],",
      ")",
      "connection.execute(",
      "    'UPDATE catalog_connections SET last_validated_at = ?'",
      "    ' WHERE last_validated_at IS NOT NULL',",
      "    [sync],",
      ")",
      "connection.execute(",
      "    'UPDATE catalog_sync_states SET last_synced_at = ?, updated_at = ?',",
      "    [sync, sync],",
      ")",
      "connection.commit()",
      "connection.close()"
   ].join("\n");

   execFileSync("uv", ["run", "--package", "kontext-studio", "python", "-"], {
      cwd: repoRoot,
      input: script,
      env: {
         ...process.env,
         DOCS_DB: server.dbFile,
         DOCS_EPOCH: String(FIXTURE_EPOCH),
         DOCS_SYNC_EPOCH: String(CAPTURE_CLOCK.getTime() - 5 * 60 * 1000),
         DOCS_NAMES: JSON.stringify(seedFiles.map((file) => file.name))
      },
      stdio: ["pipe", "ignore", "inherit"]
   });
}

async function findFixtureProject(server, token) {
   const page = await api(
      server,
      token,
      `/project/filtered?${qs({ pageIndex: 1, pageSize: 100 })}`
   );
   const project = page.items.find(
      (candidate) => candidate.projectCode === FIXTURE_PROJECT_CODE
   );
   if (!project) {
      throw new Error(
         `Fixture project "${FIXTURE_PROJECT_CODE}" is missing. ` +
            "It is created by local setup; check seed.completeSetup()."
      );
   }
   return project;
}

async function uploadMissingFiles(server, token, projectId, paths) {
   const query = qs({ projectId });
   const existing = await api(
      server,
      token,
      `/file?${query}&${qs({ pageIndex: 1, pageSize: 100 })}`
   );
   const existingNames = new Set(existing.items.map((file) => file.name));

   for (const file of seedFiles) {
      if (existingNames.has(file.name)) continue;
      const content = file.content ?? fs.readFileSync(path.join(paths.exports, file.name));
      const form = new FormData();
      form.append(
         "file",
         new Blob([content], { type: file.contentType }),
         file.name
      );
      const uploadQuery = file.prefix
         ? qs({ projectId, prefix: file.prefix })
         : query;
      await api(server, token, `/file/upload?${uploadQuery}`, {
         method: "POST",
         body: form
      });
   }
}

async function ensureCatalog(server, token, projectId, paths) {
   const query = qs({ projectId });
   const connections = await api(server, token, `/catalog/connections?${query}`);
   let connection = connections.find(
      (candidate) => candidate.displayName === catalogFixture.displayName
   );

   if (!connection) {
      connection = await api(server, token, `/catalog/connections?${query}`, {
         method: "POST",
         body: JSON.stringify({
            providerKind: catalogFixture.providerKind,
            connectionKind: catalogFixture.connectionKind,
            displayName: catalogFixture.displayName,
            description: catalogFixture.description,
            enabled: true,
            sourceCategory: catalogFixture.sourceCategory,
            authType: catalogFixture.authType,
            executionMode: catalogFixture.executionMode,
            config: {
               databasePath: paths.database,
               defaultNamespace: catalogFixture.defaultNamespace
            }
         })
      });
   }

   const sync = await api(
      server,
      token,
      `/catalog/connections/${connection.id}/sync?${query}`,
      { method: "POST" }
   );
   if (sync.status !== "succeeded") {
      throw new Error(
         `Catalog sync failed for "${catalogFixture.displayName}": ${sync.errorMessage ?? sync.status}`
      );
   }
   return connection;
}

async function ensureConcepts(server, token, projectId) {
   const query = qs({ projectId });
   for (const concept of knowledgeConcepts) {
      await api(
         server,
         token,
         `/catalog/okf/concepts/${concept.id}?${query}`,
         {
            method: "PUT",
            body: JSON.stringify(concept)
         }
      );
   }
}

async function assertFixtures(server, token, projectId) {
   const query = qs({ projectId });
   const files = await api(
      server,
      token,
      `/file?${query}&${qs({ pageIndex: 1, pageSize: 100 })}`
   );
   const names = new Set(files.items.map((file) => file.name));
   const missingFiles = fixtureExpectations.files.filter((name) => !names.has(name));
   if (missingFiles.length > 0) {
      throw new Error(
         `Fixture assertion failed: missing files ${missingFiles.join(", ")}. ` +
            `Present: ${[...names].sort().join(", ")}`
      );
   }

   const entities = await api(server, token, `/catalog/entities?${query}`);
   const entityNames = new Set(entities.map((entity) => entity.entityName));
   const missingEntities = catalogEntities.filter((name) => !entityNames.has(name));
   if (missingEntities.length > 0) {
      throw new Error(
         `Fixture assertion failed: catalog is missing ${missingEntities.join(", ")}. ` +
            `Present: ${[...entityNames].sort().join(", ") || "(none)"}`
      );
   }

   return { files: [...names].sort(), entities: [...entityNames].sort() };
}

export async function seedFixtures({ server, token }) {
   const paths = prepareFixtureData(server);
   const project = await findFixtureProject(server, token);
   await uploadMissingFiles(server, token, project.id, paths);
   const connection = await ensureCatalog(server, token, project.id, paths);
   // Runs are queued by uploads and by the catalog sync, so stabilize after both.
   stabilizeTimestamps(server);
   await ensureConcepts(server, token, project.id);
   const state = await assertFixtures(server, token, project.id);

   console.log(
      `[docs-capture] fixtures ready: ${state.files.length} files, ` +
         `${state.entities.length} catalog entities in project "${project.projectCode}".`
   );

   return { project, connection, ...state };
}
