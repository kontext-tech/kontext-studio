import type { MermaidBlockData } from "@kontext-tech/schema";
import React from "react";
import { CustomMermaid } from "./CustomMermaid";

interface MermaidBlockComponentProps {
   id?: string;
   data: MermaidBlockData;
   onChange: (data: MermaidBlockData) => void;
   readonly?: boolean;
}

export const MermaidBlockComponent: React.FC<MermaidBlockComponentProps> = ({
   id,
   data,
   onChange,
   readonly = false
}) => {
   const code = data.code || "";
   const title = data.title || "Mermaid Diagram";

   const handleChange = (newCode: string) => {
      onChange({
         ...data,
         code: newCode
      });
   };

   const handleTitleChange = (newTitle: string) => {
      onChange({
         ...data,
         title: newTitle
      });
   };

   return (
      <CustomMermaid
         id={id}
         code={code}
         title={title}
         onChange={handleChange}
         onTitleChange={handleTitleChange}
         readonly={readonly}
         className="kontext-notebook-editor mermaid-block"
      />
   );
};
