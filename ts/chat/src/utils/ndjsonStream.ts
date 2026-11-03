type SafeParseResult<T> =
   | {
        success: true;
        data: T;
     }
   | {
        success: false;
        error: {
           issues: Array<{
              message: string;
           }>;
        };
     };

interface SafeParseSchema<T> {
   safeParse: (input: unknown) => SafeParseResult<T>;
}

export async function consumeNdjsonStream<T>({
   stream,
   schema,
   onValue
}: {
   stream: ReadableStream<Uint8Array>;
   schema: SafeParseSchema<T>;
   onValue: (value: T) => Promise<void> | void;
}): Promise<void> {
   const reader = stream.getReader();
   const decoder = new TextDecoder();
   let buffer = "";

   const processBuffer = async (flush = false) => {
      const lines = buffer.split("\n");
      buffer = flush ? "" : (lines.pop() ?? "");

      for (const rawLine of lines) {
         const line = rawLine.trim();
         if (!line) {
            continue;
         }

         const parsedJson = JSON.parse(line) as unknown;
         const parsedValue = schema.safeParse(parsedJson);
         if (!parsedValue.success) {
            throw new Error(
               `Invalid NDJSON event: ${parsedValue.error.issues
                  .map((issue) => issue.message)
                  .join(", ")}`
            );
         }

         await onValue(parsedValue.data);
      }
   };

   try {
      while (true) {
         const { done, value } = await reader.read();

         if (done) {
            buffer += decoder.decode();
            await processBuffer(true);
            if (buffer.trim()) {
               throw new Error("Invalid NDJSON stream: unterminated line");
            }
            return;
         }

         buffer += decoder.decode(value, { stream: true });
         await processBuffer(false);
      }
   } finally {
      reader.releaseLock();
   }
}
