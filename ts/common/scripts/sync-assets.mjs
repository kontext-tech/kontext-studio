// Copy the assets the renderer needs into dist (replaces `mkdir -p` + glob
// `cp` commands, which do not run on Windows shells). Note: fs.cpSync with a
// `filter` option copies nothing when the filter rejects the source root on
// some Node versions, so files are selected here before copying.
import { copyFileSync, cpSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

mkdirSync("dist/assets", { recursive: true });
for (const name of readdirSync("src/assets")) {
   if (/\.(svg|png)$/.test(name)) {
      copyFileSync(join("src/assets", name), join("dist/assets", name));
   }
}
cpSync("src/resources", "dist/resources", { recursive: true });
