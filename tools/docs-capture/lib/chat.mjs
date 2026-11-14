/**
 * Chat fixtures: record one real conversation, then replay it by inserting the
 * exact message rows the harness wrote.
 *
 * Replaying rows instead of re-running a model keeps screenshots deterministic
 * and means capture never needs a provider credential. Record mode is the only
 * path that reads `OLLAMA_CLOUD_API_KEY`.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import {
   CHAT_ARTIFACTS,
   CHAT_QUESTION,
   CHAT_SESSION_ID,
   CHAT_SESSION_NAME
} from "../fixtures/chat.mjs";
import { api, queryString } from "./http.mjs";
import { repoRoot, toolsDir } from "./paths.mjs";

const MODEL_DISPLAY_NAME = "DeepSeek V4.1 Flash (Ollama Cloud)";
const MODEL_CANONICAL_ID = "ollama_cloud/deepseek-v4.1-flash";
const MODEL_ADAPTER = "ollama_native";
const MODEL_CONNECTION_KIND = "ollama_cloud";
const DEFAULT_BASE_URL = "https://ollama.com";
const TRANSCRIPT_FILE = path.join(
   toolsDir,
   "transcripts",
   "chat",
   "music-store.json"
);

export async function ensureModelConnection(
   server,
   { token, apiKey, baseUrl = DEFAULT_BASE_URL }
) {
   const existing = await api(server, token, "/model-connections");
   const found = existing.find(
      (connection) => connection.displayName === MODEL_DISPLAY_NAME
   );
   if (found) return found;

   return api(server, token, "/model-connections", {
      method: "POST",
      body: JSON.stringify({
         sourceType: "user_managed",
         adapterType: MODEL_ADAPTER,
         connectionKind: MODEL_CONNECTION_KIND,
         canonicalModelId: MODEL_CANONICAL_ID,
         displayName: MODEL_DISPLAY_NAME,
         providerConfig: { endpointBaseUrl: baseUrl },
         credentialRefs: { apiKeyRef: apiKey },
         endpointBaseUrl: baseUrl,
         isDefault: true,
         enabled: true,
         secretConfigured: true,
         validationState: "unknown"
      })
   });
}

export async function createChatSession(
   server,
   { token, projectId, modelSelectionId, catalogConnectionId }
) {
   return api(server, token, "/ai/chat/session", {
      method: "POST",
      body: JSON.stringify({
         projectId,
         sessionName: CHAT_SESSION_NAME,
         modelSelectionId,
         defaultCatalogConnectionId: catalogConnectionId ?? null
      })
   });
}

export async function streamChat(
   server,
   { token, projectId, sessionId, message, timeoutMs = 240_000 }
) {
   const controller = new AbortController();
   const timer = setTimeout(() => controller.abort(), timeoutMs);
   const response = await fetch(`${server.apiUrl}/ai/chat/stream`, {
      signal: controller.signal,
      method: "POST",
      headers: {
         Authorization: `Bearer ${token}`,
         "content-type": "application/json"
      },
      body: JSON.stringify({ projectId, sessionId, message })
   });
   if (!response.ok || !response.body) {
      throw new Error(
         `Chat stream failed with ${response.status}: ${(await response.text()).slice(0, 400)}`
      );
   }
   // Consume the NDJSON body to completion; the persisted snapshot is written on
   // the terminal event, so reading the database before the body ends races.
   const reader = response.body.getReader();
   const decoder = new TextDecoder();
   let buffer = "";
   try {
      while (true) {
         const { done, value } = await reader.read();
         if (done) break;
         buffer += decoder.decode(value, { stream: true });
      }
   } catch (error) {
      if (error?.name === "AbortError") {
         throw new Error(
            `Chat stream did not finish within ${timeoutMs / 1000}s. ` +
               "Check api.log for a queued job or a model timeout."
         );
      }
      throw error;
   } finally {
      clearTimeout(timer);
   }
   return buffer;
}

export async function readSessionMessages(server, sessionId) {
   const script = [
      "import json, os, sqlite3",
      "connection = sqlite3.connect(os.environ['DOCS_DB'])",
      "rows = connection.execute(",
      "    'select seq, message_json from agent_run_messages where session_id = ? order by seq',",
      "    (os.environ['DOCS_SESSION'],),",
      ").fetchall()",
      "connection.close()",
      "print(json.dumps([json.loads(row[1]) for row in rows]))"
   ].join("\n");

   const output = execFileSync("uv", ["run", "--package", "kontext-studio", "python", "-"], {
      cwd: repoRoot,
      input: script,
      env: {
         ...process.env,
         DOCS_DB: server.dbFile,
         DOCS_SESSION: sessionId
      },
      encoding: "utf8"
   });
   return JSON.parse(output);
}

const SECRET_PATTERNS = [
   /\bsk-[A-Za-z0-9_-]{16,}\b/,
   /\bAKIA[0-9A-Z]{16}\b/,
   /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
   /\bBearer\s+[A-Za-z0-9._~+/-]{16,}/,
   /\bgh[pousr]_[A-Za-z0-9]{20,}\b/
];

/**
 * Remove capture-local details from a recorded conversation before it is
 * committed: the temporary HOME, the checkout path, and the API key that was
 * used to record it. Then refuse to write anything that still looks like a
 * credential, because a transcript is source that ships in the repository.
 */
export function sanitizeTranscript(messages, { apiKey, homeDir } = {}) {
   let text = JSON.stringify(messages);
   if (homeDir) text = text.split(homeDir).join("~");
   text = text.split(repoRoot).join("~/kontext-studio");
   if (apiKey) text = text.split(apiKey).join("docs-fixture-key");

   for (const pattern of SECRET_PATTERNS) {
      const match = text.match(pattern);
      if (match) {
         throw new Error(
            `Recorded transcript contains a credential-like value (${match[0].slice(0, 8)}...). ` +
               "Remove it from the model response before committing the transcript."
         );
      }
   }
   return JSON.parse(text);
}

export function writeTranscript({ messages, apiKey, homeDir }) {
   const sanitized = sanitizeTranscript(messages, { apiKey, homeDir });
   fs.mkdirSync(path.dirname(TRANSCRIPT_FILE), { recursive: true });
   fs.writeFileSync(
      TRANSCRIPT_FILE,
      `${JSON.stringify({ sessionName: CHAT_SESSION_NAME, messages: sanitized }, null, 3)}\n`
   );
   return TRANSCRIPT_FILE;
}

export function readTranscript() {
   if (!fs.existsSync(TRANSCRIPT_FILE)) return null;
   return JSON.parse(fs.readFileSync(TRANSCRIPT_FILE, "utf8"));
}

/**
 * Insert the recorded session and its messages into a fresh capture database.
 * Chat session ids are UUID columns (stored as 32-char hex by SQLAlchemy);
 * `agent_run_messages.session_id` is a plain string holding the dashed id.
 */
export function seedChatTranscript(server, { projectId, modelSelectionId, epoch }) {
   const transcript = readTranscript();
   if (!transcript) {
      throw new Error(`No chat transcript at ${TRANSCRIPT_FILE}. Run \`pnpm docs:record\` first.`);
   }
   const script = [
      "import datetime, json, os, sqlite3, uuid",
      "connection = sqlite3.connect(os.environ['DOCS_DB'])",
      "transcript = json.load(open(os.environ['DOCS_TRANSCRIPT'], encoding='utf-8'))",
      "profile = connection.execute('select id from local_profile limit 1').fetchone()",
      "owner = profile[0] if profile else None",
      "stamp = datetime.datetime.fromtimestamp(",
      "    int(os.environ['DOCS_EPOCH']) / 1000, datetime.UTC",
      ").strftime('%Y-%m-%d %H:%M:%S.%f')",
      "session = os.environ['DOCS_SESSION_ID']",
      "project = os.environ['DOCS_PROJECT_ID']",
      "connection.execute('delete from agent_run_messages where session_id = ?', (session,))",
      "connection.execute('delete from chat_sessions where id = ?', (session.replace('-', ''),))",
      "connection.execute(",
      "    'insert into chat_sessions (id, project_id, session_name, model_selection_id, python_execution_approval_mode, tokens_inbound, tokens_outbound, created_by, created_at, updated_at, is_deleted, owner_id) values (?,?,?,?,?,?,?,?,?,?,?,?)',",
      "    (session.replace('-', ''), project.replace('-', ''), transcript['sessionName'], os.environ['DOCS_MODEL_ID'], 'always_ask', 0, 0, owner, stamp, stamp, 0, owner),",
      ")",
      "connection.execute('delete from chat_session_token_usage where project_id = ?', (project.replace('-', ''),))",
      "stamp_dt = datetime.datetime.fromtimestamp(int(os.environ['DOCS_EPOCH']) / 1000, datetime.UTC)",
      "for offset in range(6):",
      "    year, month = stamp_dt.year, stamp_dt.month - offset",
      "    while month <= 0:",
      "        month += 12",
      "        year -= 1",
      "    consumed = stamp_dt.replace(year=year, month=month, day=12, hour=12, minute=0, second=0, microsecond=0)",
      "    token_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'kontext-docs-token-{offset}'))",
      "    connection.execute(",
      "        'insert into chat_session_token_usage (id, chat_session_id, job_run_id, project_id, model_selection_id, tokens_inbound, tokens_outbound, consumed_at, created_at) values (?,?,?,?,?,?,?,?,?)',",
      "        (token_id.replace('-', ''), session.replace('-', ''), None, project.replace('-', ''), os.environ['DOCS_MODEL_ID'], 12000 + offset * 1500, 8000 + offset * 900, consumed.strftime('%Y-%m-%d %H:%M:%S.%f'), consumed.strftime('%Y-%m-%d %H:%M:%S.%f')),",
      "    )",
      "for index, message in enumerate(transcript['messages']):",
      "    message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'kontext-docs-chat-message-{index}'))",
      "    connection.execute(",
      "        'insert into agent_run_messages (id, session_id, seq, message_json) values (?,?,?,?)',",
      "        (message_id.replace('-', ''), session, index, json.dumps(message)),",
      "    )",
      "connection.execute('delete from chat_session_artifacts where session_id = ?', (session.replace('-', ''),))",
      "for index, artifact in enumerate(json.loads(os.environ['DOCS_ARTIFACTS'])):",
      "    row = connection.execute(",
      "        'select id from files where name = ? and is_deleted = 0 order by date_created limit 1',",
      "        (artifact['name'],),",
      "    ).fetchone()",
      "    if not row:",
      "        raise SystemExit(f\"Missing artifact fixture file: {artifact['name']}\")",
      "    artifact_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'kontext-docs-chat-artifact-{index}'))",
      "    connection.execute(",
      "        'insert into chat_session_artifacts (id, session_id, artifact_id, artifact_type, title, meta, created_at, updated_at, deleted_at) values (?,?,?,?,?,?,?,?,?)',",
      "        (artifact_id.replace('-', ''), session.replace('-', ''), row[0], artifact['artifactType'], artifact['title'], None, stamp, stamp, None),",
      "    )",
      "connection.commit()",
      "connection.close()"
   ].join("\n");

   execFileSync("uv", ["run", "--package", "kontext-studio", "python", "-"], {
      cwd: repoRoot,
      input: script,
      env: {
         ...process.env,
         DOCS_DB: server.dbFile,
         DOCS_TRANSCRIPT: TRANSCRIPT_FILE,
         DOCS_EPOCH: String(epoch),
         DOCS_SESSION_ID: CHAT_SESSION_ID,
         DOCS_PROJECT_ID: projectId,
         DOCS_MODEL_ID: modelSelectionId ?? "",
         DOCS_ARTIFACTS: JSON.stringify(CHAT_ARTIFACTS)
      },
      stdio: ["pipe", "ignore", "inherit"]
   });
}

export async function recordChat(
   server,
   { token, projectId, apiKey, baseUrl, catalogConnectionId }
) {
   const connection = await ensureModelConnection(server, { token, apiKey, baseUrl });
   const session = await createChatSession(server, {
      token,
      projectId,
      modelSelectionId: connection.id,
      catalogConnectionId
   });
   await streamChat(server, {
      token,
      projectId,
      sessionId: session.id,
      message: CHAT_QUESTION
   });
   const messages = await readSessionMessages(server, session.id);
   if (messages.length === 0) {
      throw new Error(
         "The chat run finished but wrote no messages. Check the model connection and the server log."
      );
   }
   return { session, messages };
}

export { CHAT_SESSION_ID, CHAT_SESSION_NAME, CHAT_QUESTION, TRANSCRIPT_FILE };
