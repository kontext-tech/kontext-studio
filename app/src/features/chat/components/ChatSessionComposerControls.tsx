import type { PythonExecutionApprovalMode } from "@kontext-tech/schema";
import { SettingOutlined } from "@kontext-tech/icons";
import { Button, Dropdown, theme } from "antd";

export interface ChatSessionComposerControlsProps {
   pythonExecutionApprovalMode: PythonExecutionApprovalMode;
   onPythonExecutionApprovalModeChange: (
      mode: PythonExecutionApprovalMode
   ) => Promise<void> | void;
   disabled?: boolean;
}

const ChatSessionComposerControls = ({
   pythonExecutionApprovalMode,
   onPythonExecutionApprovalModeChange,
   disabled = false
}: ChatSessionComposerControlsProps) => {
   const { token } = theme.useToken();
   const approvalOptions: Array<{
      value: PythonExecutionApprovalMode;
      label: string;
   }> = [
      {
         value: "always_ask",
         label: "Ask first"
      },
      {
         value: "auto_approve",
         label: "Auto execution"
      }
   ];
   const selectedOption =
      approvalOptions.find(
         (option) => option.value === pythonExecutionApprovalMode
      ) || approvalOptions[0];
   const buttonStyle = {
      color: token.colorTextSecondary,
      maxWidth: 120,
      minWidth: 0,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "flex-start",
      fontSize: token.fontSizeSM,
      height: 24,
      paddingInline: 4
   } as const;
   const labelStyle = {
      display: "block",
      minWidth: 0,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
   } as const;

   return (
      <Dropdown
         trigger={["click"]}
         disabled={disabled}
         menu={{
            items: [
               {
                  type: "group",
                  label: "Code execution",
                  children: approvalOptions.map((option) => ({
                     key: `approval:${option.value}`,
                     label: option.label
                  }))
               }
            ],
            selectedKeys: [`approval:${pythonExecutionApprovalMode}`],
            onClick: ({ key }) => {
               const value = String(key);

               if (value.startsWith("approval:")) {
                  void onPythonExecutionApprovalModeChange(
                     value.replace(
                        "approval:",
                        ""
                     ) as PythonExecutionApprovalMode
                  );
               }
            }
         }}
      >
         <Button
            type="text"
            size="small"
            disabled={disabled}
            title="Session settings"
            aria-label="Session settings"
            icon={<SettingOutlined />}
            style={buttonStyle}
         >
            <span style={labelStyle}>{selectedOption.label}</span>
         </Button>
      </Dropdown>
   );
};

export default ChatSessionComposerControls;
