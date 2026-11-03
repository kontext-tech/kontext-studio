import { useCallback, useState } from "react";
import { useNotebookServices } from "../context/NotebookServiceContext";
import type {
   CellExecutionContext,
   CellExecutionResult
} from "../types/bindings";

export function useExecuteCell(language: string) {
   const { executionEngine } = useNotebookServices();
   const [isExecuting, setIsExecuting] = useState(false);
   const [result, setResult] = useState<CellExecutionResult | null>(null);

   const execute = useCallback(
      async (
         code: string,
         context?: CellExecutionContext
      ): Promise<CellExecutionResult> => {
         if (!executionEngine) {
            const nextResult: CellExecutionResult = {
               status: "error",
               error: "No execution engine bound"
            };
            setResult(nextResult);
            return nextResult;
         }

         setIsExecuting(true);

         try {
            let nextResult: CellExecutionResult;

            if (executionEngine.executeCell) {
               nextResult = await executionEngine.executeCell(
                  language,
                  code,
                  context
               );
            } else {
               const unifiedResult = await executionEngine.execute(
                  code,
                  context,
                  language
               );
               nextResult = {
                  status: unifiedResult.status,
                  output: unifiedResult.outputs,
                  error: unifiedResult.error,
                  executionTimeMs: unifiedResult.executionTimeMs
               };
            }

            setResult(nextResult);
            return nextResult;
         } catch (error) {
            const nextResult: CellExecutionResult = {
               status: "error",
               error: error instanceof Error ? error.message : "Unknown error"
            };
            setResult(nextResult);
            return nextResult;
         } finally {
            setIsExecuting(false);
         }
      },
      [executionEngine, language]
   );

   const cancel = useCallback(
      async (context?: CellExecutionContext): Promise<boolean> => {
         if (!executionEngine?.cancelExecution) {
            return false;
         }

         const cancelled = await executionEngine.cancelExecution(context);
         return cancelled;
      },
      [executionEngine]
   );

   return {
      execute,
      cancel,
      isExecuting,
      result,
      setResult
   };
}
