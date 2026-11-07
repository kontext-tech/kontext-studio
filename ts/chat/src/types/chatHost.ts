import type { ApiErrorResult } from "@kontext-tech/common";
import type {
   Artifact,
   ModelCatalogEntry,
   ProjectModel
} from "@kontext-tech/schema";
import type React from "react";

export interface ChatAvailabilityContext {
   project: ProjectModel;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
}

export interface ChatNavigationAdapter {
   onSessionCreated: (params: {
      project: ProjectModel;
      sessionId: string;
      initialMessage: string;
   }) => void | Promise<void>;
}

export interface ChatArtifactRenderParams {
   artifact: Artifact;
   onTitleChange: (title: string) => void;
}

export interface ChatArtifactHost {
   renderArtifactContent: (params: ChatArtifactRenderParams) => React.ReactNode;
}

export interface ChatInputSelectionOptions {
   foundationModels?: ModelCatalogEntry[];
   modelSelectionId?: string | undefined;
}
