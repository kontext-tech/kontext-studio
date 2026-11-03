import PageContainer from "@/components/layout/SeoPageContainer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { RouteNames } from "@/types";
import { ProfileManager } from "@kontext-tech/account";
import {
   EDIT_MODE,
   MODE_QUERY_PARAM,
   TAB_QUERY_PARAM
} from "@kontext-tech/common";
import { UserOutlined } from "@kontext-tech/icons";
import { useSiteCultures } from "@kontext-tech/site";
import { useUiFeedback } from "@kontext-tech/ui";
import { Col, Row, Space, Tabs } from "antd";
import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

const DEFAULT_TAB_ACCOUNT_PAGE = "profile";

const AccountPage = () => {
   const [searchParams, setSearchParams] = useSearchParams();
   const apiErrorHandler = useApiErrorHandler();
   const ui = useUiFeedback();
   const currentTab =
      searchParams.get(TAB_QUERY_PARAM) || DEFAULT_TAB_ACCOUNT_PAGE;
   const isEditMode = searchParams.get(MODE_QUERY_PARAM) === EDIT_MODE;
   const { cultures, loading: culturesLoading } = useSiteCultures({
      errorHandler: apiErrorHandler
   });
   const languageOptions = useMemo(
      () =>
         cultures.map((culture) => ({
            value: culture.code,
            label: culture.nativeName
         })),
      [cultures]
   );

   // Map tab keys to their display names for the page title
   const tabDisplayName = useMemo(() => {
      const tabNames: Record<string, string> = {
         [DEFAULT_TAB_ACCOUNT_PAGE]: "Profile"
      };
      return tabNames[currentTab] || "Profile";
   }, [currentTab]);

   const pageHeaderTitle = "Account Settings";

   // Callback to remove the mode query parameter
   const handleEditComplete = useCallback(() => {
      const newSearchParams = new URLSearchParams(searchParams);
      newSearchParams.delete(MODE_QUERY_PARAM);
      setSearchParams(newSearchParams);
   }, [searchParams, setSearchParams]);

   return (
      <PageContainer
         key={`account-settings-${currentTab}`}
         title={pageHeaderTitle}
         subTitle={tabDisplayName}
         description="Manage your profile and preferences."
         routeName={RouteNames.ACCOUNT_SETTINGS}
         type="website"
         showBreadcrumb={false}
      >
         <Tabs
            activeKey={currentTab}
            onChange={(key) => setSearchParams({ [TAB_QUERY_PARAM]: key })}
            items={[
               {
                  key: DEFAULT_TAB_ACCOUNT_PAGE,
                  label: (
                     <Space>
                        <UserOutlined />
                        Profile
                     </Space>
                  ),
                  children: (
                     <Row justify="start">
                        <Col xs={24} sm={24} md={20} lg={16} xl={14}>
                           <ProfileManager
                              initialEditMode={isEditMode}
                              onEditComplete={handleEditComplete}
                              errorHandler={apiErrorHandler}
                              ui={ui}
                              languageOptions={languageOptions}
                              languageOptionsLoading={culturesLoading}
                           />
                        </Col>
                     </Row>
                  )
               }
            ]}
         />
      </PageContainer>
   );
};

export default AccountPage;
