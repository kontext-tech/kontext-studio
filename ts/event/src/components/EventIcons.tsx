import {
   BellMinusOutlined,
   BellPlusOutlined,
   DatabaseOutlined,
   EditOutlined,
   ExclamationCircleOutlined,
   EyeOutlined,
   FileAddOutlined,
   FileTextOutlined,
   GlobalOutlined,
   HistoryOutlined,
   KeyOutlined,
   LockOutlined,
   MailPlusOutlined,
   MailsOutlined,
   SafetyOutlined,
   StopOutlined,
   UnlockOutlined,
   UserAddOutlined,
   UserCheckOutlined,
   UserOutlined
} from "@kontext-labs/icons";
import { EventType } from "@kontext-labs/schema";
import React from "react";

export const getEventIcon = (type: EventType | undefined): React.ReactNode => {
   if (!type) return <HistoryOutlined />;

   switch (type) {
      case EventType.Login:
         return <SafetyOutlined />;
      case EventType.EditProfile:
         return <UserOutlined />;
      case EventType.ChangePassword:
         return <KeyOutlined />;
      case EventType.Enable2FA:
         return <LockOutlined />;
      case EventType.Disable2FA:
         return <UnlockOutlined />;
      case EventType.EnableUser:
         return <UserCheckOutlined />;
      case EventType.DisableUser:
         return <StopOutlined />;
      case EventType.Register:
         return <UserAddOutlined />;

      case EventType.SubscribeToGroup:
         return <BellPlusOutlined />;
      case EventType.UnsubscribeFromGroup:
         return <BellMinusOutlined />;

      case EventType.CreateServiceAccount:
         return <UserAddOutlined />;
      case EventType.EnableServiceAccount:
         return <UserCheckOutlined />;
      case EventType.DisableServiceAccount:
         return <StopOutlined />;
      case EventType.AuthenticateServiceAccount:
         return <SafetyOutlined />;
      case EventType.CreateServiceAccountKey:
         return <KeyOutlined />;
      case EventType.EnableServiceAccountKey:
         return <KeyOutlined />;
      case EventType.DisableServiceAccountKey:
         return <StopOutlined />;
      case EventType.DeleteServiceAccountKey:
         return <ExclamationCircleOutlined />;

      case EventType.ConfirmEmail:
         return <MailsOutlined />;
      case EventType.RequestCampaignEmailDelivery:
         return <MailPlusOutlined />;

      case EventType.CreateFile:
         return <FileAddOutlined />;
      case EventType.CreateFiles:
         return <FileAddOutlined />;
      case EventType.DeleteFile:
         return <ExclamationCircleOutlined />;
      case EventType.UpdateFileSchema:
         return <EditOutlined />;

      case EventType.CreateCatalogEntity:
         return <DatabaseOutlined />;
      case EventType.UpdateCatalogEntity:
         return <EditOutlined />;
      case EventType.DeleteCatalogEntity:
         return <ExclamationCircleOutlined />;

      case EventType.ProcessFailedEvent:
         return <ExclamationCircleOutlined />;

      case EventType.CreateProject:
         return <GlobalOutlined />;
      case EventType.ModifyProject:
         return <EditOutlined />;
      case EventType.ViewProject:
         return <EyeOutlined />;
      case EventType.ViewPage:
         return <FileTextOutlined />;

      case EventType.Other:
         return <HistoryOutlined />;

      default:
         return <FileTextOutlined />;
   }
};
