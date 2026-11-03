import {
   CodeOutlined,
   DownloadOutlined,
   EditOutlined,
   ExpandAltOutlined
} from "@kontext-labs/icons";
import {
   Alert,
   Button,
   Flex,
   Input,
   Modal,
   Tooltip,
   Typography,
   theme
} from "antd";
import { Mermaid } from "@ant-design/x";
import React, { useRef, useState } from "react";

const { Text } = Typography;

export interface CustomMermaidProps {
   id?: string;
   code: string;
   onChange?: (code: string) => void;
   onTitleChange?: (title: string) => void;
   readonly?: boolean;
   title?: string;
   className?: string;
   style?: React.CSSProperties;
}

export const CustomMermaid: React.FC<CustomMermaidProps> = ({
   id,
   code,
   onChange,
   onTitleChange,
   readonly = false,
   title = "Mermaid Diagram",
   className,
   style
}) => {
   const { token } = theme.useToken();
   const [isEditModalOpen, setIsEditModalOpen] = useState(false);
   const [isMaxModalOpen, setIsMaxModalOpen] = useState(false);
   const [isTitleModalOpen, setIsTitleModalOpen] = useState(false);
   const [draftCode, setDraftCode] = useState(code);
   const [tempTitle, setTempTitle] = useState(title);
   const containerRef = useRef<HTMLDivElement>(null);
   const diagramRef = useRef<HTMLDivElement>(null);

   // Use a simple hash for the key to avoid using the entire code string as a key
   const codeHash = React.useMemo(() => {
      let hash = 0;
      for (let i = 0; i < code.length; i++) {
         const char = code.charCodeAt(i);
         hash = (hash << 5) - hash + char;
         hash |= 0; // Convert to 32bit integer
      }
      return (id ? `${id}-` : "") + Math.abs(hash).toString(16);
   }, [code, id]);

   const handleOpenEditModal = () => {
      setDraftCode(code);
      setIsEditModalOpen(true);
   };

   const handleSave = () => {
      onChange?.(draftCode);
      setIsEditModalOpen(false);
   };

   const handleOpenTitleModal = () => {
      setTempTitle(title);
      setIsTitleModalOpen(true);
   };

   const handleTitleSave = () => {
      onTitleChange?.(tempTitle);
      setIsTitleModalOpen(false);
   };

   const handleDownload = () => {
      // Look for the SVG inside our diagram container
      const svg =
         diagramRef.current?.querySelector("svg") ||
         containerRef.current?.querySelector(".ant-mermaid-graph svg");

      if (svg) {
         // Create a clone to modify for export
         const clonedSvg = svg.cloneNode(true) as SVGSVGElement;
         clonedSvg.setAttribute("xmlns", "http://www.w3.org/2000/svg");

         const svgData = new XMLSerializer().serializeToString(clonedSvg);
         const blob = new Blob([svgData], {
            type: "image/svg+xml;charset=utf-8"
         });
         const url = URL.createObjectURL(blob);
         const link = document.createElement("a");
         link.href = url;
         link.download = `${title.replace(/\s+/g, "_")}.svg`;
         document.body.appendChild(link);
         link.click();
         document.body.removeChild(link);
         URL.revokeObjectURL(url);
      }
   };

   const SummaryCard = (
      <div
         className="mermaid-block__card"
         style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: 12,
            borderBottom: "1px solid var(--editor-border)",
            background: "var(--editor-bg-secondary)",
            gap: 12
         }}
      >
         <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Text strong ellipsis style={{ maxWidth: 360 }}>
               {title}
            </Text>
         </div>
         <Flex gap={4}>
            {!readonly && (
               <>
                  <Tooltip title="Rename">
                     <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={handleOpenTitleModal}
                        style={{ minWidth: 0 }}
                     />
                  </Tooltip>
                  {onChange && (
                     <Tooltip title="Edit diagram">
                        <Button
                           type="text"
                           size="small"
                           icon={<CodeOutlined />}
                           onClick={handleOpenEditModal}
                           style={{ minWidth: 0 }}
                        />
                     </Tooltip>
                  )}
               </>
            )}
            <Tooltip title="Maximize">
               <Button
                  type="text"
                  size="small"
                  icon={<ExpandAltOutlined />}
                  onClick={() => setIsMaxModalOpen(true)}
                  style={{ minWidth: 0 }}
                  disabled={code.trim().length === 0}
               />
            </Tooltip>
            <Tooltip title="Download SVG">
               <Button
                  type="text"
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={handleDownload}
                  style={{ minWidth: 0 }}
                  disabled={code.trim().length === 0}
               />
            </Tooltip>
         </Flex>
      </div>
   );

   return (
      <div
         className={`kontext-mermaid-block ${className || ""}`}
         style={{ marginBottom: token.marginSM, ...style }}
         ref={containerRef}
      >
         <div
            style={{
               border: "1px solid var(--editor-border)",
               borderRadius: 8,
               overflow: "hidden",
               background: token.colorBgContainer
            }}
         >
            {SummaryCard}
            <div
               ref={diagramRef}
               className="mermaid-block__diagram"
               style={{ padding: 12 }}
            >
               {code.trim().length === 0 ? (
                  <Alert
                     type="info"
                     showIcon
                     banner
                     description={
                        readonly
                           ? "No diagram code provided."
                           : "Add Mermaid code to render a diagram."
                     }
                  />
               ) : (
                  <Mermaid
                     key={codeHash}
                     header={null}
                     styles={{
                        root: { border: "none", background: "transparent" }
                     }}
                  >
                     {code}
                  </Mermaid>
               )}
            </div>
         </div>

         <Modal
            title={title}
            open={isMaxModalOpen}
            onCancel={() => setIsMaxModalOpen(false)}
            footer={null}
            width="90vw"
            zIndex={1100}
            styles={{ body: { maxHeight: "75vh", overflow: "auto" } }}
            destroyOnHidden
         >
            <Mermaid key={codeHash} header={null}>
               {code}
            </Mermaid>
         </Modal>

         <Modal
            title="Edit Mermaid Diagram"
            open={isEditModalOpen}
            onOk={handleSave}
            onCancel={() => setIsEditModalOpen(false)}
            okText="Save"
            cancelText="Cancel"
            width={720}
            zIndex={1001}
         >
            <Flex vertical gap={12} style={{ marginTop: 8 }}>
               <Input.TextArea
                  placeholder={"Mermaid code (e.g. flowchart TD\\nA-->B)"}
                  value={draftCode}
                  autoSize={{ minRows: 8, maxRows: 20 }}
                  onChange={(e) => setDraftCode(e.target.value)}
               />
            </Flex>
         </Modal>

         <Modal
            title="Edit Mermaid Block Title"
            open={isTitleModalOpen}
            onOk={handleTitleSave}
            onCancel={() => setIsTitleModalOpen(false)}
            okText="Save"
            cancelText="Cancel"
            width={400}
            zIndex={1001}
         >
            <Input
               value={tempTitle}
               onChange={(e) => setTempTitle(e.target.value)}
               placeholder="Enter title..."
               autoFocus
               onPressEnter={handleTitleSave}
               style={{ marginTop: 8 }}
            />
         </Modal>
      </div>
   );
};
