// Copy the assets the renderer needs into dist (replaces `mkdir -p` + glob
// `cp` commands, which do not run on Windows shells).
import { cpSync } from "node:fs";

cpSync("src/assets", "dist/assets", {
   filter: (source) => /\.(svg|png)$/.test(source)
});
cpSync("src/resources", "dist/resources", { recursive: true });
