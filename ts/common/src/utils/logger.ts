/**
 * Single logging surface for workspace packages and the app.
 *
 * Policy:
 * - `logger.debug` is for trace-level breadcrumbs. Dev consoles show it;
 *   production builds strip it (terser `pure_funcs`).
 * - `logger.info` is for meaningful lifecycle events; stripped in prod bundles
 *   by the same build rule.
 * - `logger.warn` / `logger.error` always ship — failures must be diagnosable
 *   in production.
 *
 * `console` is banned elsewhere (`no-console` lint rule), so new diagnostics
 * must go through this module.
 */
import { isDevelopment } from "./envUtils";

type Level = "debug" | "info" | "warn" | "error";

const enabledFor = (level: Level): boolean =>
   level === "warn" || level === "error" || isDevelopment();

const write = (level: Level, prefix: string, args: unknown[]): void => {
   if (!enabledFor(level)) {
      return;
   }

   const line = args.length === 1 ? args[0] : [prefix, ...args];
   /* eslint-disable no-console */
   if (level === "error") console.error(line);
   else if (level === "warn") console.warn(line);
   else if (level === "info") console.info(line);
   else console.log(line);
   /* eslint-enable no-console */
};

export const logger = {
   debug: (prefix: string, ...args: unknown[]) => write("debug", prefix, args),
   info: (prefix: string, ...args: unknown[]) => write("info", prefix, args),
   warn: (prefix: string, ...args: unknown[]) => write("warn", prefix, args),
   error: (prefix: string, ...args: unknown[]) => write("error", prefix, args)
};

export type Logger = typeof logger;
