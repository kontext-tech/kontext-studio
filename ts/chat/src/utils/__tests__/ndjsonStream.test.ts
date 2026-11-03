/// <reference types="jest" />

import { ReadableStream } from "stream/web";
import { TextDecoder, TextEncoder } from "util";
import { RunEvent, SimpleRunEventStreamSchema } from "@kontext-tech/schema";
import { consumeNdjsonStream } from "../ndjsonStream";

const encoder = new TextEncoder();
(
   globalThis as typeof globalThis & { TextDecoder: typeof TextDecoder }
).TextDecoder = TextDecoder;

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
   return new ReadableStream<Uint8Array>({
      start(controller) {
         chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
         controller.close();
      }
   });
}

describe("consumeNdjsonStream", () => {
   it("parses and validates NDJSON across chunk boundaries", async () => {
      const events: string[] = [];

      await consumeNdjsonStream({
         stream: streamFromChunks([
            '{"eventType":"RunContent","content":"hel',
            'lo"}\n{"eventType":"RunCompleted"}\n'
         ]),
         schema: SimpleRunEventStreamSchema,
         onValue: (event) => {
            events.push(event.eventType);
         }
      });

      expect(events).toEqual([RunEvent.RunContent, RunEvent.RunCompleted]);
   });

   it("throws on invalid event payloads", async () => {
      await expect(
         consumeNdjsonStream({
            stream: streamFromChunks(['{"eventType":"Nope"}\n']),
            schema: SimpleRunEventStreamSchema,
            onValue: () => undefined
         })
      ).rejects.toThrow(/Invalid NDJSON event/);
   });

   it("preserves tool-call and paused-run payloads", async () => {
      const events: unknown[] = [];

      await consumeNdjsonStream({
         stream: streamFromChunks([
            '{"eventType":"ToolCallStarted","eventData":{"tool":{"toolCallId":"tool-1","toolName":"delegate_to_agent","toolArgs":{"agentName":"Notebook Agent"}}}}\n',
            '{"eventType":"RunPaused","eventData":{"runId":"run-1","toolCalls":[{"toolCallId":"tool-2","toolName":"approve_python_execution","toolArgs":{"code":"print(1)"}}]}}\n',
            '{"eventType":"ToolCallCompleted","eventData":{"tool":{"toolCallId":"tool-1","toolName":"delegate_to_agent","result":"delegated"}}}\n'
         ]),
         schema: SimpleRunEventStreamSchema,
         onValue: (event) => {
            events.push(event);
         }
      });

      expect(events).toEqual([
         expect.objectContaining({
            eventType: RunEvent.ToolCallStarted,
            eventData: expect.objectContaining({
               tool: expect.objectContaining({
                  toolCallId: "tool-1",
                  toolName: "delegate_to_agent"
               })
            })
         }),
         expect.objectContaining({
            eventType: RunEvent.RunPaused,
            eventData: expect.objectContaining({
               runId: "run-1",
               toolCalls: [
                  expect.objectContaining({
                     toolCallId: "tool-2",
                     toolName: "approve_python_execution"
                  })
               ]
            })
         }),
         expect.objectContaining({
            eventType: RunEvent.ToolCallCompleted,
            eventData: expect.objectContaining({
               tool: expect.objectContaining({
                  toolCallId: "tool-1",
                  toolName: "delegate_to_agent"
               })
            })
         })
      ]);
   });
});
