import BreadcrumbNav from "@/components/layout/BreadcrumbNav";
import { useProject } from "@kontext-labs/project";
import { useRoute } from "@/hooks/useRoute";
import { PageHeaderBase, type PageHeaderBaseProps } from "@kontext-labs/layout";
import React, { type ReactNode } from "react";

interface PageHeaderProps extends Omit<
   PageHeaderBaseProps,
   "breadcrumb" | "variant"
> {
   /**
    * Page title to display
    */
   title: string;

   /**
    * Action buttons or other elements to display on the right side
    */
   actions?: ReactNode;

   /**
    * Additional content to display below the header (e.g., description, alert)
    */
   subContent?: ReactNode;

   /**
    * Header variant
    * - document: standard hero-style header for scrolling pages (default)
    * - application: fixed-height header with bottom border for full-height application views
    */
   variant?: "document" | "application";

   /**
    * Editable title support (for application variant)
    */
   onSaveTitle?: (newTitle: string) => Promise<void> | void;
   isSaving?: boolean;
   isTitleEditable?: boolean;

   /**
    * Custom breadcrumb override
    */
   breadcrumb?: ReactNode;

   /**
    * Show breadcrumb navigation (default: false)
    */
   showBreadcrumb?: boolean;
}

/**
 * Standardized PageHeader component with support for document and application layouts
 */
const PageHeader: React.FC<PageHeaderProps> = ({
   title,
   actions,
   subContent,
   variant = "document",
   onSaveTitle,
   isSaving = false,
   isTitleEditable = false,
   breadcrumb,
   showBreadcrumb = false
}) => {
   const { currentRoute } = useRoute();
   const { currentProject } = useProject();

   const defaultBreadcrumb =
      breadcrumb === null
         ? null
         : breadcrumb ||
           (showBreadcrumb && currentRoute && (
              <div style={{ marginBottom: variant === "document" ? 16 : 4 }}>
                 <BreadcrumbNav
                    routeName={currentRoute.name}
                    project={currentProject}
                 />
              </div>
           ));

   return (
      <PageHeaderBase
         title={title}
         actions={actions}
         subContent={subContent}
         variant={variant}
         onSaveTitle={onSaveTitle}
         isSaving={isSaving}
         isTitleEditable={isTitleEditable}
         breadcrumb={defaultBreadcrumb}
      />
   );
};

export default PageHeader;
