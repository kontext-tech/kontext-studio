import type {
   FoundationModel,
   ModelConnection,
   ModelConnectionCredentialRefs,
   ModelConnectionProviderConfig,
   ModelCredentialRefField,
   ModelProviderConfigField,
   ModelProviderDefinition
} from "@kontext-tech/schema";

export type CredentialFieldName =
   "apiKeyRef" | "accessKeyIdRef" | "secretAccessKeyRef" | "sessionTokenRef";

type CredentialFieldMeta = {
   label: string;
   placeholder: string;
   createHelp: string;
   editHelp: string;
};

type ProviderFormCopy = {
   basicsDescription: string;
   authDescription: string;
   displayNamePlaceholder: string;
   endpointPlaceholder?: string;
};

const VALIDATION_STATE_META: Record<
   string,
   { color: "default" | "error" | "processing" | "success"; label: string }
> = {
   valid: { color: "success", label: "Ready" },
   pending: { color: "processing", label: "Pending" },
   invalid: { color: "error", label: "Needs attention" },
   unknown: { color: "default", label: "Unknown" }
};

const CREDENTIAL_FIELD_META: Record<CredentialFieldName, CredentialFieldMeta> =
   {
      apiKeyRef: {
         label: "API Key",
         placeholder: "sk-...",
         createHelp:
            "Leave blank if this provider does not require an API key.",
         editHelp: "Leave blank to keep the existing API key."
      },
      accessKeyIdRef: {
         label: "AWS Access Key ID",
         placeholder: "AKIA...",
         createHelp: "Enter the AWS access key ID for this Bedrock connection.",
         editHelp: "Leave blank to keep the existing access key ID."
      },
      secretAccessKeyRef: {
         label: "AWS Secret Access Key",
         placeholder: "AWS secret access key",
         createHelp:
            "Enter the AWS secret access key for this Bedrock connection.",
         editHelp: "Leave blank to keep the existing secret access key."
      },
      sessionTokenRef: {
         label: "AWS Session Token",
         placeholder: "Optional session token",
         createHelp:
            "Optional. Add this if your AWS credentials use a session token.",
         editHelp: "Leave blank to keep the existing session token."
      }
   };

const PROVIDER_FORM_COPY: Record<string, ProviderFormCopy> = {
   lm_studio: {
      basicsDescription:
         "Point this connection at an LM Studio server and choose the curated model you want available across chats and tools.",
      authDescription:
         "LM Studio often works without authentication, but you can keep an API key here if your setup expects one.",
      displayNamePlaceholder: "My LM Studio Gemma 4",
      endpointPlaceholder: "http://localhost:1234/v1"
   },
   ollama: {
      basicsDescription:
         "Connect Ollama through its OpenAI-compatible endpoint and choose which curated model should back this connection.",
      authDescription:
         "Most Ollama setups do not require credentials. Add an API key only if you are fronting it with an authenticated gateway.",
      displayNamePlaceholder: "My Ollama Gemma 4",
      endpointPlaceholder: "http://localhost:11434/v1"
   },
   openai: {
      basicsDescription:
         "Choose an OpenAI model, give the connection a clear name, and keep any endpoint override with the rest of the provider settings.",
      authDescription:
         "OpenAI connections require an API key before they can be used.",
      displayNamePlaceholder: "OpenAI GPT-5.4 Mini",
      endpointPlaceholder: "https://api.openai.com/v1"
   },
   anthropic: {
      basicsDescription:
         "Choose a Claude model and configure the connection details you want available to the rest of the platform.",
      authDescription:
         "Anthropic connections require an API key before they can be used.",
      displayNamePlaceholder: "Anthropic Claude Sonnet 4.6"
   },
   gemini: {
      basicsDescription:
         "Choose a Gemini model and configure the connection details you want available to chats and AI tools.",
      authDescription:
         "Gemini connections require an API key before they can be used.",
      displayNamePlaceholder: "Google Gemini 2.5 Flash"
   },
   bedrock: {
      basicsDescription:
         "Choose the curated Bedrock model, set the AWS region for this connection, and keep the connection name friendly for the rest of your team.",
      authDescription:
         "Bedrock uses per-connection AWS credentials in this rollout, with optional session token support.",
      displayNamePlaceholder: "AWS Bedrock Nova 2 Lite"
   },
   openrouter: {
      basicsDescription:
         "Choose a curated model, point the connection at OpenRouter, and keep a readable connection name for future chats and tools.",
      authDescription:
         "OpenRouter connections require an API key before they can be used.",
      displayNamePlaceholder: "OpenRouter GPT-4o Mini",
      endpointPlaceholder: "https://openrouter.ai/api/v1"
   },
   deepseek: {
      basicsDescription:
         "Choose a DeepSeek model and keep a readable connection name for future chats and tools.",
      authDescription:
         "DeepSeek connections require an API key before they can be used.",
      displayNamePlaceholder: "DeepSeek Chat",
      endpointPlaceholder: "https://api.deepseek.com/v1"
   },
   ollama_cloud: {
      basicsDescription:
         "Choose an Ollama Cloud model served from ollama.com and keep a readable connection name.",
      authDescription:
         "Ollama Cloud connections require an API key before they can be used.",
      displayNamePlaceholder: "Ollama Cloud GPT OSS 120B",
      endpointPlaceholder: "https://ollama.com"
   },
   google_vertex: {
      basicsDescription:
         "Choose a Vertex AI Gemini model and provide the Google Cloud project it should run in.",
      authDescription:
         "Vertex AI uses Application Default Credentials (gcloud auth application-default login) or a Google Cloud API key, plus a project and location.",
      displayNamePlaceholder: "Vertex AI Gemini 2.5 Flash",
      endpointPlaceholder: "https://us-central1-aiplatform.googleapis.com"
   },
   azure_openai: {
      basicsDescription:
         "Point this connection at an Azure OpenAI deployment and name the deployment as the model.",
      authDescription:
         "Azure OpenAI connections require an API key and endpoint, optionally with an API version.",
      displayNamePlaceholder: "Azure OpenAI GPT-4o Mini",
      endpointPlaceholder: "https://my-resource.openai.azure.com"
   },
   mistral: {
      basicsDescription:
         "Choose a Mistral model and keep a readable connection name for future chats and tools.",
      authDescription:
         "Mistral connections require an API key before they can be used.",
      displayNamePlaceholder: "Mistral Small",
      endpointPlaceholder: "https://api.mistral.ai/v1"
   },
   openai_compatible: {
      basicsDescription:
         "Point this connection at any endpoint that exposes the OpenAI API schema.",
      authDescription: "Add an API key if the endpoint requires one.",
      displayNamePlaceholder: "My OpenAI-compatible endpoint"
   }
};

export function getValidationMeta(validationState?: string | null) {
   return (
      VALIDATION_STATE_META[validationState ?? "unknown"] ||
      VALIDATION_STATE_META.unknown
   );
}

export function getProviderDefinition(
   providerDefinitions: ModelProviderDefinition[],
   connectionKind?: string | null
) {
   return providerDefinitions.find(
      (definition) => definition.connectionKind === connectionKind
   );
}

function toStringSet<T extends string>(values: T[]): Set<T> {
   return new Set(values.filter(Boolean));
}

export function getEffectiveConfigFields(
   providerDefinition?: ModelProviderDefinition
): {
   required: Set<ModelProviderConfigField>;
   optional: Set<ModelProviderConfigField>;
} {
   return {
      required: toStringSet(providerDefinition?.requiredConfigFields ?? []),
      optional: toStringSet(providerDefinition?.optionalConfigFields ?? [])
   };
}

export function getEffectiveCredentialFields(
   providerDefinition?: ModelProviderDefinition
): {
   required: Set<ModelCredentialRefField>;
   optional: Set<ModelCredentialRefField>;
} {
   return {
      required: toStringSet(providerDefinition?.requiredCredentialFields ?? []),
      optional: toStringSet(providerDefinition?.optionalCredentialFields ?? [])
   };
}

export function getVisibleCredentialFields(
   providerDefinition?: ModelProviderDefinition
): CredentialFieldName[] {
   const effectiveFields = getEffectiveCredentialFields(providerDefinition);
   const orderedFields: CredentialFieldName[] = [
      "apiKeyRef",
      "accessKeyIdRef",
      "secretAccessKeyRef",
      "sessionTokenRef"
   ];
   return orderedFields.filter(
      (field) =>
         effectiveFields.required.has(field) ||
         effectiveFields.optional.has(field)
   );
}

export function getDefaultEndpointBaseUrl(
   providerDefinition?: ModelProviderDefinition
): string | undefined {
   return providerDefinition?.defaultEndpointBaseUrl || undefined;
}

export function getProviderFormCopy(
   connectionKind?: string | null
): ProviderFormCopy {
   return (
      PROVIDER_FORM_COPY[connectionKind ?? ""] ||
      PROVIDER_FORM_COPY.openai_compatible
   );
}

export function getCredentialFieldMeta(fieldName: CredentialFieldName) {
   return CREDENTIAL_FIELD_META[fieldName];
}

export function getConfiguredCredentialLabels(
   connection?: ModelConnection | null
): string[] {
   const labels: string[] = [];
   const credentialRefs = connection?.credentialRefs;
   if (credentialRefs?.apiKeyRef || connection?.secretRef) {
      labels.push(CREDENTIAL_FIELD_META.apiKeyRef.label);
   }
   if (credentialRefs?.accessKeyIdRef) {
      labels.push(CREDENTIAL_FIELD_META.accessKeyIdRef.label);
   }
   if (credentialRefs?.secretAccessKeyRef) {
      labels.push(CREDENTIAL_FIELD_META.secretAccessKeyRef.label);
   }
   if (credentialRefs?.sessionTokenRef) {
      labels.push(CREDENTIAL_FIELD_META.sessionTokenRef.label);
   }
   return labels;
}

function modelSupportsProvider(
   model: FoundationModel,
   connectionKind?: string | null
) {
   const supportedKinds = new Set<string>(model.supportedConnectionKinds ?? []);
   return (
      supportedKinds.size === 0 ||
      !connectionKind ||
      supportedKinds.has(connectionKind)
   );
}

export function filterFoundationModelsForProvider(
   models: FoundationModel[],
   connectionKind?: string | null
) {
   return models.filter((model) =>
      modelSupportsProvider(model, connectionKind)
   );
}

export function getProviderLabel(
   connectionKind: string,
   providerDefinitions: ModelProviderDefinition[]
) {
   return (
      getProviderDefinition(providerDefinitions, connectionKind)?.displayName ||
      connectionKind
   );
}

export function pruneProviderConfig(
   providerConfig: ModelConnectionProviderConfig | undefined,
   providerDefinition?: ModelProviderDefinition
): ModelConnectionProviderConfig | undefined {
   if (!providerConfig) {
      return undefined;
   }
   const effectiveFields = getEffectiveConfigFields(providerDefinition);
   const visibleFields = new Set([
      ...effectiveFields.required,
      ...effectiveFields.optional
   ]);

   const nextConfig: ModelConnectionProviderConfig = {};
   if (
      (visibleFields.has("endpointBaseUrl") ||
         providerDefinition?.supportsCustomEndpoint) &&
      providerConfig.endpointBaseUrl
   ) {
      nextConfig.endpointBaseUrl = providerConfig.endpointBaseUrl;
   }
   if (visibleFields.has("region") && providerConfig.region) {
      nextConfig.region = providerConfig.region;
   }
   if (visibleFields.has("projectId") && providerConfig.projectId) {
      nextConfig.projectId = providerConfig.projectId;
   }
   if (visibleFields.has("location") && providerConfig.location) {
      nextConfig.location = providerConfig.location;
   }
   if (visibleFields.has("apiVersion") && providerConfig.apiVersion) {
      nextConfig.apiVersion = providerConfig.apiVersion;
   }

   return Object.keys(nextConfig).length > 0 ? nextConfig : undefined;
}

export function pruneCredentialRefs(
   credentialRefs: Partial<ModelConnectionCredentialRefs> | undefined,
   providerDefinition?: ModelProviderDefinition
): ModelConnectionCredentialRefs | undefined {
   if (!credentialRefs) {
      return undefined;
   }
   const visibleFields = new Set(
      getVisibleCredentialFields(providerDefinition)
   );
   const nextRefs: ModelConnectionCredentialRefs = {};

   if (visibleFields.has("apiKeyRef") && credentialRefs.apiKeyRef) {
      nextRefs.apiKeyRef = credentialRefs.apiKeyRef;
   }
   if (visibleFields.has("accessKeyIdRef") && credentialRefs.accessKeyIdRef) {
      nextRefs.accessKeyIdRef = credentialRefs.accessKeyIdRef;
   }
   if (
      visibleFields.has("secretAccessKeyRef") &&
      credentialRefs.secretAccessKeyRef
   ) {
      nextRefs.secretAccessKeyRef = credentialRefs.secretAccessKeyRef;
   }
   if (visibleFields.has("sessionTokenRef") && credentialRefs.sessionTokenRef) {
      nextRefs.sessionTokenRef = credentialRefs.sessionTokenRef;
   }

   return Object.keys(nextRefs).length > 0 ? nextRefs : undefined;
}
