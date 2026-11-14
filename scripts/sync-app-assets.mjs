// Sync shared assets and the built frontend into the packages that consume
// them. Ported from scripts/sync-app-assets.sh so the Windows desktop build
// does not depend on resolving a non-WSL `bash` on the PATH.
import {
   copyFileSync,
   cpSync,
   existsSync,
   mkdirSync,
   readdirSync,
   rmSync
} from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../", import.meta.url));

const sharedPublic = join(ROOT, "ts/common/public");
const sharedAssets = join(ROOT, "ts/common/src/assets");
const appPublic = join(ROOT, "app/public");

if (existsSync(sharedPublic)) {
   console.log("Syncing app assets...");
   mkdirSync(appPublic, { recursive: true });
   if (existsSync(join(sharedPublic, "icons"))) {
      rmSync(join(appPublic, "icons"), { recursive: true, force: true });
      cpSync(join(sharedPublic, "icons"), join(appPublic, "icons"), {
         recursive: true
      });
   }
   mkdirSync(join(appPublic, "resources"), { recursive: true });
   for (const name of readdirSync(sharedAssets)) {
      if (name.startsWith("logo")) {
         copyFileSync(
            join(sharedAssets, name),
            join(appPublic, "resources", name)
         );
      }
   }
   for (const name of readdirSync(appPublic)) {
      if (name.startsWith("logo")) {
         rmSync(join(appPublic, name));
      }
   }
   console.log(`Synced to ${appPublic}`);
} else {
   console.warn(
      `Warning: shared public directory not found at ${sharedPublic}`
   );
}

const appDist = join(ROOT, "app/dist");
const appDistTarget = join(
   ROOT,
   "py/kontext-studio/src/kontext/studio/_app_dist"
);

if (existsSync(appDist)) {
   console.log("Syncing built app/dist into kontext-studio package...");
   rmSync(appDistTarget, { recursive: true, force: true });
   mkdirSync(appDistTarget, { recursive: true });
   cpSync(appDist, appDistTarget, { recursive: true });
   for (const name of [
      "LICENSE",
      "THIRD_PARTY_NOTICES.md",
      "TERMS.md",
      "PRIVACY.md"
   ]) {
      copyFileSync(join(ROOT, name), join(appDistTarget, name));
   }
   console.log(`Synced app/dist to ${appDistTarget}`);
} else {
   console.log(
      "Note: app/dist not built yet. Run 'pnpm --filter @kontext-tech/app build' to bundle frontend UI."
   );
}

console.log("Asset sync complete.");
