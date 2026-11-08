// `tauri-build` validates the configured resource paths at compile time. A
// fresh checkout has no assembled runtime yet, so create empty placeholders
// for `cargo check`/`clippy` in PR validation.
import fs from "node:fs";

for (const dir of [
   "desktop/src-tauri/resources/python",
   "desktop/src-tauri/resources/wheelhouse"
]) {
   fs.mkdirSync(dir, { recursive: true });
}
