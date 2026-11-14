// Copy src/styles into dist/styles (replaces `cp -R src/styles/. dist/styles/`,
// which does not run on Windows shells).
import { cpSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });
cpSync("src/styles", "dist/styles", { recursive: true });
