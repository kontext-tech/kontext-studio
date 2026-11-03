import { CloseOutlined, PanelLeftCloseOutlined } from "@kontext-labs/icons";
import type { Artifact } from "@kontext-labs/schema";
import { ArtifactType } from "@kontext-labs/schema";
import { Button, Card, Flex, Tabs, Typography, theme } from "antd";
import React from "react";
import { useChatSessionStore } from "../stores/chatSessionStore";
import ArtifactTypeIcon from "./ArtifactTypeIcon";

const { Text } = Typography;

export interface ArtifactsSidebarRenderParams {
   artifact: Artifact;
   onTitleChange: (title: string) => void;
}

export interface ArtifactsSidebarProps {
   artifacts: Artifact[];
   onClose?: () => void;
   onRemoveArtifact?: (artifactId: string) => void;
   onAutoRename?: (title: string) => void;
   renderArtifactContent: (
      params: ArtifactsSidebarRenderParams
   ) => React.ReactNode;
}

const getArtifactTypeLabel = (type: string) => {
   switch (type) {
      case ArtifactType.DataTable:
         return "Data Table";
      case ArtifactType.Notebook:
         return "Notebook";
      case ArtifactType.Chart:
         return "Chart";
      case ArtifactType.Image:
         return "Image";
      default:
         return "Artifact";
   }
};

const ArtifactsSidebar: React.FC<ArtifactsSidebarProps> = ({
   artifacts,
   onClose,
   onRemoveArtifact,
   onAutoRename,
   renderArtifactContent
}) => {
   const { token } = theme.useToken();
   const [tabTitles, setTabTitles] = React.useState<Record<string, string>>({});
   const [autoRenameCandidate, setAutoRenameCandidate] = React.useState<{
      artifactId: string;
      title: string;
   } | null>(null);
   const activeArtifactId = useChatSessionStore(
      (state) => state.activeArtifactId
   );
   const setActiveArtifact = useChatSessionStore(
      (state) => state.setActiveArtifact
   );
   const chatSession = useChatSessionStore((state) => state.chatSession);
   const hasAutoRenamedRef = React.useRef(false);
   const chromeRowHeight = "var(--app-chrome-row-height, 56px)";

   React.useEffect(() => {
      if (artifacts.length > 0 && !activeArtifactId) {
         setActiveArtifact(artifacts[0].artifactId);
      }
   }, [artifacts, activeArtifactId, setActiveArtifact]);

   React.useEffect(() => {
      if (
         !onAutoRename ||
         hasAutoRenamedRef.current ||
         !autoRenameCandidate ||
         artifacts.length === 0 ||
         !chatSession ||
         !chatSession.sessionName.startsWith("Chat - ")
      ) {
         return;
      }

      if (
         artifacts[0].artifactId === autoRenameCandidate.artifactId &&
         autoRenameCandidate.title &&
         autoRenameCandidate.title !== "Untitled"
      ) {
         onAutoRename(autoRenameCandidate.title);
         hasAutoRenamedRef.current = true;
      }
   }, [artifacts, autoRenameCandidate, chatSession, onAutoRename]);

   const visibleTabTitles = React.useMemo(() => {
      const currentArtifactIds = new Set(
         artifacts.map((artifact) => artifact.artifactId)
      );

      return Object.fromEntries(
         Object.entries(tabTitles).filter(([artifactId]) =>
            currentArtifactIds.has(artifactId)
         )
      );
   }, [artifacts, tabTitles]);

   const updateTabTitle = React.useCallback(
      (artifactId: string, title: string) => {
         setTabTitles((prev) => {
            if (prev[artifactId] === title) {
               return prev;
            }

            return { ...prev, [artifactId]: title };
         });
         setAutoRenameCandidate({ artifactId, title });
      },
      []
   );

   const tabItems = React.useMemo(
      () =>
         artifacts.map((artifact) => ({
            key: artifact.artifactId,
            label: (
               <Flex
                  align="center"
                  gap="xs"
                  style={{
                     paddingLeft: 8,
                     minHeight: chromeRowHeight
                  }}
               >
                  <ArtifactTypeIcon
                     type={artifact.artifactType as ArtifactType}
                  />
                  <span
                     style={{
                        maxWidth: "200px",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap"
                     }}
                  >
                     {visibleTabTitles[artifact.artifactId] ||
                        artifact.title ||
                        getArtifactTypeLabel(artifact.artifactType)}
                  </span>
                  {onRemoveArtifact && (
                     <Button
                        type="text"
                        size="small"
                        icon={<CloseOutlined />}
                        onClick={(event) => {
                           event.stopPropagation();
                           onRemoveArtifact(artifact.artifactId);
                        }}
                        style={{ marginLeft: "auto" }}
                     />
                  )}
               </Flex>
            ),
            children: (
               <div
                  style={{
                     height: "100%",
                     overflow: "hidden",
                     display: "flex",
                     flexDirection: "column"
                  }}
               >
                  {renderArtifactContent({
                     artifact,
                     onTitleChange: (title) =>
                        updateTabTitle(artifact.artifactId, title)
                  })}
               </div>
            )
         })),
      [
         artifacts,
         onRemoveArtifact,
         renderArtifactContent,
         updateTabTitle,
         visibleTabTitles
      ]
   );

   return (
      <Flex
         vertical
         style={{
            height: "100%",
            overflow: "hidden"
         }}
      >
         {onClose && (
            <Flex
               align="center"
               justify="flex-start"
               style={{
                  minHeight: chromeRowHeight,
                  padding: "0 8px",
                  flexShrink: 0
               }}
            >
               <Button
                  type="text"
                  icon={<PanelLeftCloseOutlined />}
                  onClick={onClose}
                  size="small"
               />
            </Flex>
         )}

         {artifacts.length === 0 ? (
            <div style={{ padding: "8px", flexShrink: 0 }}>
               <Card size="small">
                  <Text type="secondary" style={{ textAlign: "center" }}>
                     No artifacts yet. Start a conversation to generate
                     notebooks, charts, and data tables.
                  </Text>
               </Card>
            </div>
         ) : (
            <Tabs
               type="line"
               size="small"
               items={tabItems}
               activeKey={activeArtifactId || undefined}
               onChange={setActiveArtifact}
               destroyOnHidden={true}
               style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  minHeight: 0,
                  overflow: "hidden"
               }}
               tabBarStyle={{
                  margin: 0,
                  flexShrink: 0,
                  minHeight: chromeRowHeight,
                  paddingLeft: token.paddingXS,
                  paddingRight: token.paddingXS
               }}
               styles={{
                  header: {
                     margin: 0,
                     minHeight: chromeRowHeight
                  },
                  item: {
                     paddingTop: 0,
                     paddingBottom: 0,
                     minHeight: chromeRowHeight,
                     display: "flex",
                     alignItems: "center"
                  }
               }}
            />
         )}
      </Flex>
   );
};

export default ArtifactsSidebar;
