import { Prompts, Welcome } from "@ant-design/x";
import { RobotOutlined, Wand2Outlined } from "@kontext-tech/icons";
import { theme, Typography } from "antd";
import React from "react";

export interface ChatWelcomeProps {
   onPromptClick: (message: string) => void;
   title?: React.ReactNode;
   description?: React.ReactNode;
   style?: React.CSSProperties;
   showWelcome?: boolean;
   showPrompts?: boolean;
   showGetStarted?: boolean;
   displayName?: string;
   docsHref?: string;
}

const ChatWelcome = ({
   onPromptClick,
   title,
   description,
   style,
   showWelcome = true,
   showPrompts = true,
   showGetStarted = false,
   displayName = "there",
   docsHref
}: ChatWelcomeProps) => {
   const { token } = theme.useToken();

   const gradientStyle = {
      ["--gradient-start"]: token.colorPrimary,
      ["--gradient-end"]: token.colorInfo
   } as unknown as React.CSSProperties;

   const defaultDescription = showGetStarted ? (
      <span>
         Start a conversation to explore your project data, create insights and
         notebooks. New to Kontext?{" "}
         {docsHref ? (
            <Typography.Link href={docsHref} target="_blank">
               Learn how to get started
            </Typography.Link>
         ) : (
            "Learn how to get started"
         )}
      </span>
   ) : (
      "Start a conversation to explore your project data, create insights and notebooks."
   );

   return (
      <div
         style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "16px",
            ...style
         }}
      >
         {showWelcome && (
            <Welcome
               variant="borderless"
               icon={
                  <span className="gradient-text" style={gradientStyle}>
                     <RobotOutlined
                        className="gradient-text"
                        style={{ fontSize: "48px" }}
                     />
                  </span>
               }
               title={
                  title || (
                     <span>
                        {" "}
                        Hello,{" "}
                        <span className="gradient-text" style={gradientStyle}>
                           {displayName}
                        </span>
                        !
                     </span>
                  )
               }
               description={description || defaultDescription}
            />
         )}

         {showPrompts && (
            <div style={{ width: "100%", maxWidth: "600px" }}>
               <Typography.Paragraph
                  type="secondary"
                  style={{ textAlign: "center", marginBottom: "16px" }}
               >
                  Not sure where to start?
               </Typography.Paragraph>
               <Prompts
                  items={[
                     {
                        key: "suggest-questions",
                        description:
                           "Suggest three questions based on the data in the project",
                        icon: (
                           <Wand2Outlined
                              style={{ color: token.colorPrimary }}
                           />
                        )
                     }
                  ]}
                  onItemClick={(info) => {
                     onPromptClick(String(info.data.description ?? ""));
                  }}
                  style={{
                     width: "100%"
                  }}
                  vertical
               />
            </div>
         )}
      </div>
   );
};

export default ChatWelcome;
