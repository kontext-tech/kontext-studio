import { GlobalOutlined, LockOutlined } from "@kontext-tech/icons";
import { AccessLevel } from "@kontext-tech/schema";
import { Tag, theme } from "antd";

export type AccessLevelTagProps = {
   accessLevel: AccessLevel;
   showIcon?: boolean;
   style?: React.CSSProperties;
   showLabel?: boolean;
};

const AccessLevelTag = ({
   accessLevel,
   showIcon = true,
   style,
   showLabel = true
}: AccessLevelTagProps) => {
   const { token } = theme.useToken();

   const getAccessLevelDisplay = () => {
      switch (accessLevel) {
         case AccessLevel.Public:
            return {
               icon: (
                  <GlobalOutlined style={{ color: token.colorTextSecondary }} />
               ),
               label: "Public"
            };
         case AccessLevel.Private:
            return {
               icon: <LockOutlined style={{ color: token.colorError }} />,
               label: "Private"
            };
         default:
            return {
               icon: (
                  <LockOutlined style={{ color: token.colorTextDisabled }} />
               ),
               label: "Unknown"
            };
      }
   };

   const { icon, label } = getAccessLevelDisplay();

   return (
      <Tag
         style={{
            fontWeight: "normal",
            border: "none",
            color: token.colorTextSecondary,
            ...style
         }}
         icon={showIcon ? icon : undefined}
      >
         {showLabel ? label : null}
      </Tag>
   );
};

export default AccessLevelTag;
