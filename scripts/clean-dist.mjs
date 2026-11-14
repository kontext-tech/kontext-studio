// Cross-platform `rm -rf` for package build scripts, invoked from ts/* as
// `node ../../scripts/clean-dist.mjs dist tsconfig.tsbuildinfo`. Paths are
// resolved against the caller's working directory.
import { rmSync } from "node:fs";

for (const path of process.argv.slice(2)) {
   rmSync(path, { recursive: true, force: true });
}
