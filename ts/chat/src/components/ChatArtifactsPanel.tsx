import type { Artifact } from "@kontext-labs/schema";
import React from "react";
import type { ChatArtifactHost } from "../types/chatHost";
import ArtifactsSidebar from "./ArtifactsSidebar";

export interface ChatArtifactsPanelProps {
   artifacts: Artifact[];
   host: ChatArtifactHost;
   onClose?: () => void;
   onRemoveArtifact?: (artifactId: string) => void;
   onAutoRename?: (title: string) => void;
}

const ChatArtifactsPanel: React.FC<ChatArtifactsPanelProps> = ({
   artifacts,
   host,
   onClose,
   onRemoveArtifact,
   onAutoRename
}) => {
   return (
      <ArtifactsSidebar
         artifacts={artifacts}
         onClose={onClose}
         onRemoveArtifact={onRemoveArtifact}
         onAutoRename={onAutoRename}
         renderArtifactContent={host.renderArtifactContent}
      />
   );
};

export default ChatArtifactsPanel;
