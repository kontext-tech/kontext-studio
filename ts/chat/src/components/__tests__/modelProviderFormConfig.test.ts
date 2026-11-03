/// <reference types="jest" />

import type {
   FoundationModel,
   ModelProviderDefinition
} from "@kontext-tech/schema";
import {
   filterFoundationModelsForProvider,
   pruneCredentialRefs,
   pruneProviderConfig
} from "../modelProviderFormConfig";

const providerDefinitions: ModelProviderDefinition[] = [
   {
      connectionKind: "openai_compatible",
      displayName: "OpenAI-Compatible",
      adapterType: "openai_compatible",
      requiredConfigFields: ["endpointBaseUrl"],
      optionalConfigFields: [],
      requiredCredentialFields: [],
      optionalCredentialFields: ["apiKeyRef"],
      supportsCustomEndpoint: true
   },
   {
      connectionKind: "bedrock",
      displayName: "AWS Bedrock",
      adapterType: "bedrock_native",
      requiredConfigFields: ["region"],
      optionalConfigFields: [],
      requiredCredentialFields: ["accessKeyIdRef", "secretAccessKeyRef"],
      optionalCredentialFields: ["sessionTokenRef"],
      supportsCustomEndpoint: false
   }
];

const foundationModels: FoundationModel[] = [
   {
      canonicalModelId: "google/gemma-4-26b-a4b",
      name: "Google Gemma 4 26B A4B",
      vendor: "Google",
      adapterType: "openai_compatible",
      capabilities: ["chat"],
      reasoningSupported: false,
      supportedConnectionKinds: ["lm_studio", "ollama"],
      providerModelAliases: {}
   },
   {
      canonicalModelId: "deepseek/deepseek-chat",
      name: "DeepSeek Chat",
      vendor: "DeepSeek",
      adapterType: "openai_compatible",
      capabilities: ["chat", "reasoning"],
      reasoningSupported: true,
      supportedConnectionKinds: ["deepseek"],
      providerModelAliases: {
         deepseek: "deepseek-chat"
      }
   },
   {
      canonicalModelId: "openai/gpt-4o-mini",
      name: "OpenAI GPT-4o Mini",
      vendor: "OpenAI",
      adapterType: "openai_native",
      capabilities: ["chat"],
      reasoningSupported: true,
      supportedConnectionKinds: ["openai", "openrouter"],
      providerModelAliases: { openai: "gpt-4o-mini" }
   }
];

describe("modelProviderFormConfig", () => {
   it("filters curated models by provider kind", () => {
      const filtered = filterFoundationModelsForProvider(
         foundationModels,
         "deepseek"
      );

      expect(filtered.map((model) => model.canonicalModelId)).toEqual([
         "deepseek/deepseek-chat"
      ]);
   });

   it("keeps only the credential refs supported by the selected provider", () => {
      const bedrockDefinition = providerDefinitions[1];
      const refs = pruneCredentialRefs(
         {
            apiKeyRef: "sk-test",
            accessKeyIdRef: "AKIA123",
            secretAccessKeyRef: "secret",
            sessionTokenRef: "token"
         },
         bedrockDefinition
      );

      expect(refs).toEqual({
         accessKeyIdRef: "AKIA123",
         secretAccessKeyRef: "secret",
         sessionTokenRef: "token"
      });
   });

   it("retains the vertex project and location config fields", () => {
      const vertexDefinition: ModelProviderDefinition = {
         connectionKind: "google_vertex",
         displayName: "Google Vertex AI",
         adapterType: "google_vertex_native",
         requiredConfigFields: ["projectId"],
         optionalConfigFields: ["location"],
         requiredCredentialFields: [],
         optionalCredentialFields: ["apiKeyRef"],
         supportsCustomEndpoint: false
      };

      const config = pruneProviderConfig(
         {
            projectId: "my-project",
            location: "us-central1",
            endpointBaseUrl: "https://should-be-dropped"
         },
         vertexDefinition
      );

      expect(config).toEqual({
         projectId: "my-project",
         location: "us-central1"
      });
   });
});
