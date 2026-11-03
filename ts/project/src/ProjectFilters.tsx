import { PROJECT_ROLE_FILTER_OPTIONS } from "@kontext-labs/auth";
import { useUser } from "@kontext-labs/identity";
import {
   FilterOutlined,
   GlobalOutlined,
   ReloadOutlined,
   SearchOutlined
} from "@kontext-labs/icons";
import { DebouncedSearch } from "@kontext-labs/ui";
import { Button, Card, Flex, Select, Space, Switch, theme } from "antd";
import type { ReactNode } from "react";

export interface ProjectFiltersProps {
   searchText?: string;
   roleFilters: string[] | undefined;
   includePublic?: boolean;
   onSearch?: (value: string) => void;
   onRoleFilterChange: (values: string[]) => void;
   onIncludePublicChange?: (checked: boolean) => void;
   onResetFilters: () => void;
   showSearch?: boolean;
   showPublicToggle?: boolean;
   showRoleFilter?: boolean;
   title?: string;
   cardStyle?: React.CSSProperties;
   searchPrefix?: ReactNode;
   searchPlaceholder?: string;
}

const ProjectFilters = ({
   searchText = "",
   roleFilters,
   includePublic = false,
   onSearch,
   onRoleFilterChange,
   onIncludePublicChange,
   onResetFilters,
   showSearch = false,
   showPublicToggle = false,
   showRoleFilter,
   title = "Filters",
   cardStyle,
   searchPrefix = <SearchOutlined />,
   searchPlaceholder = "Search projects..."
}: ProjectFiltersProps) => {
   const { token } = theme.useToken();
   const { isAuthenticated } = useUser();
   const shouldShowRoleFilter =
      (showRoleFilter ?? isAuthenticated) && !!onRoleFilterChange;

   return (
      <Card
         size="small"
         style={{
            background: token.colorBgElevated,
            width: "100%",
            ...cardStyle
         }}
      >
         <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
            <Flex align="center" justify="space-between">
               <span style={{ fontWeight: "bold", fontSize: "16px" }}>
                  <FilterOutlined /> {title}
               </span>
            </Flex>

            {showSearch && onSearch ? (
               <DebouncedSearch
                  key={searchText}
                  placeholder={searchPlaceholder}
                  allowClear
                  style={{ width: "100%" }}
                  onSearch={onSearch}
                  defaultValue={searchText}
                  prefix={searchPrefix}
               />
            ) : null}

            {showPublicToggle && onIncludePublicChange ? (
               <Flex align="center" justify="space-between">
                  <span style={{ display: "flex", alignItems: "center" }}>
                     <GlobalOutlined style={{ marginRight: "8px" }} />
                     Include Public
                  </span>
                  <Switch
                     size="small"
                     checked={includePublic}
                     onChange={onIncludePublicChange}
                  />
               </Flex>
            ) : null}

            {shouldShowRoleFilter ? (
               <Select
                  mode="multiple"
                  allowClear
                  style={{ width: "100%", borderRadius: "8" }}
                  placeholder="Filter by role"
                  value={roleFilters || []}
                  onChange={onRoleFilterChange}
                  options={PROJECT_ROLE_FILTER_OPTIONS}
               />
            ) : null}

            <Button
               onClick={onResetFilters}
               variant="outlined"
               icon={<ReloadOutlined />}
            >
               Reset
            </Button>
         </Space>
      </Card>
   );
};

export default ProjectFilters;
