/**
 * Notebook-scoped SQL block alias validation helpers.
 *
 * A SQL block's result table is addressable inside its notebook by a stable
 * alias ("df_1", "sales_summary", ...) instead of its UUID. Python blocks load
 * it with `await kontext.load_data(alias)`; a name binds to the block's
 * results server-side when saved/run (Jupyter-style binding), never on typing
 * alone — the client only validates *user renames*.
 *
 * The pattern mirrors the `alias` field on `SqlBlockData` in @kontext-labs/schema.
 */

import type { NotebookBlock, SqlBlockData } from "@kontext-labs/schema";

const SQL_ALIAS_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;

function isValidSqlAlias(alias: string): boolean {
   return SQL_ALIAS_PATTERN.test(alias);
}

export function sqlLoadDataSnippet(alias: string): string {
   return `await kontext.load_data("${alias}")`;
}

/** Alias of a SQL block, if declared. */
function sqlBlockAlias(block: NotebookBlock): string | undefined {
   if (block.type !== "sql") {
      return undefined;
   }
   return (block.data as SqlBlockData | undefined)?.alias || undefined;
}

/** Declared SQL block aliases with their owning block ids. */
function collectSqlAliases(
   blocks: readonly NotebookBlock[]
): Array<{ blockId: string; alias: string }> {
   const declared: Array<{ blockId: string; alias: string }> = [];
   for (const block of blocks) {
      const alias = sqlBlockAlias(block);
      if (alias) {
         declared.push({ blockId: String(block.id), alias });
      }
   }
   return declared;
}

/** Validation error for a prospective rename, or null when valid. */
export function findSqlAliasError(
   alias: string,
   blocks: readonly NotebookBlock[],
   selfBlockId: string
): string | null {
   if (!isValidSqlAlias(alias)) {
      return "Use letters, numbers and underscores, starting with a letter or underscore.";
   }
   for (const { blockId, alias: existing } of collectSqlAliases(blocks)) {
      if (blockId !== selfBlockId && existing === alias) {
         return `Alias "${alias}" is already used by another SQL block in this notebook.`;
      }
   }
   return null;
}
