import fs from "node:fs";
import path from "node:path";

// Drift guard for the agent documentation topology.
//
// AGENTS.md (repo root) is the canonical always-on guide for every coding
// agent. Tool-specific entry points (`.github/copilot-instructions.md`,
// `.clinerules`, `CLAUDE.md`) are thin adapters that must point back at it,
// and procedural workflows live on-demand under `.github/skills/<name>/SKILL.md`.
//
// This script fails when a skill directory is broken, an adapter stops
// referencing the canonical sources, or the Claude symlink is severed.

const rootDir = process.cwd();
const skillsRoot = path.join(rootDir, ".github", "skills");
const adapters = [
   path.join(rootDir, ".github", "copilot-instructions.md"),
   path.join(rootDir, ".clinerules"),
];
const symlinkPath = path.join(rootDir, "CLAUDE.md");
const canonicalPath = "AGENTS.md";

const violations = [];

// 1. Every skill directory carries a valid SKILL.md with frontmatter.
if (!fs.existsSync(skillsRoot)) {
   violations.push(".github/skills/ directory is missing.");
} else {
   for (const entry of fs.readdirSync(skillsRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const skillFile = path.join(skillsRoot, entry.name, "SKILL.md");
      if (!fs.existsSync(skillFile)) {
         violations.push(`.github/skills/${entry.name}/ is missing SKILL.md.`);
         continue;
      }
      const content = fs.readFileSync(skillFile, "utf8");
      const frontmatter = /^---\n([\s\S]*?)\n---/.exec(content);
      if (!frontmatter) {
         violations.push(`.github/skills/${entry.name}/SKILL.md has no frontmatter.`);
         continue;
      }
      const name = /(?:^|\n)name:\s*(\S+)/.exec(frontmatter[1])?.[1];
      const description = /(?:^|\n)description:\s*(.+)/.exec(frontmatter[1])?.[1];
      if (name !== entry.name) {
         violations.push(
            `.github/skills/${entry.name}/SKILL.md frontmatter name '${name}' does not match the directory.`
         );
      }
      if (!description || description.length < 20) {
         violations.push(
            `.github/skills/${entry.name}/SKILL.md needs a meaningful description (loaded on demand by agents).`
         );
      }
   }
}

// 2. Adapters must reference the canonical guide (no silent forks of content).
for (const adapter of adapters) {
   if (!fs.existsSync(adapter)) {
      violations.push(`Missing adapter ${path.relative(rootDir, adapter)}.`);
      continue;
   }
   const content = fs.readFileSync(adapter, "utf8");
   if (!content.includes(canonicalPath)) {
      violations.push(
         `${path.relative(rootDir, adapter)} must reference ${canonicalPath} (adapters hold no unique content).`
      );
   }
}

// 3. The Claude entry point must track the canonical guide via symlink.
let symlinkTarget = null;
try {
   symlinkTarget = fs.readlinkSync(symlinkPath);
} catch {
   violations.push(
      `${path.relative(rootDir, symlinkPath)} must be a symlink to ${canonicalPath} (or must exist).`
   );
}
if (symlinkTarget !== null && path.normalize(symlinkTarget) !== canonicalPath) {
   violations.push(
      `${path.relative(rootDir, symlinkPath)} links to '${symlinkTarget}' but must link to ${canonicalPath}.`
   );
}

// 4. AGENTS.md must stay discoverable in the other direction: it lists every
//    adapter so each starting point reaches the canonical guide.
const agentsPath = path.join(rootDir, canonicalPath);
if (fs.existsSync(agentsPath)) {
   const agents = fs.readFileSync(agentsPath, "utf8");
   for (const adapter of adapters) {
      const referenced = path.basename(adapter);
      if (!agents.includes(referenced)) {
         violations.push(`${canonicalPath} must list adapter '${referenced}'.`);
      }
   }
   if (!fs.existsSync(symlinkPath)) {
      violations.push(`${canonicalPath} does not exist (required canonical guide).`);
   }
} else {
   violations.push(`${canonicalPath} is missing from the repository root.`);
}

if (violations.length > 0) {
   console.error("Agent documentation topology is inconsistent:");
   for (const violation of violations) {
      console.error(`  - ${violation}`);
   }
   process.exit(1);
}

console.log("Agent documentation topology is consistent.");
