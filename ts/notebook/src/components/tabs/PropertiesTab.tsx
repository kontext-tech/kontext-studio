import { normalizeTag, validateTagFormat } from "@kontext-tech/common";
import { LanguageSelect } from "@kontext-tech/ui";
import type { CultureInfoModel } from "@kontext-tech/schema";
import { Checkbox, Form, Select } from "antd";
import React from "react";

const validateTags = (_: unknown, value: string[]) => {
   if (!value) return Promise.resolve();

   const invalidTags = value.filter((tag) => !validateTagFormat(tag));
   if (invalidTags.length > 0) {
      return Promise.reject(
         "Tags can only contain letters, numbers, spaces, and dashes"
      );
   }
   return Promise.resolve();
};

interface PropertiesTabProps {
   cultures?: CultureInfoModel[];
   readonly?: boolean;
   showArticleFields?: boolean;
   /** Whether to show the "Save as draft" option in article fields - defaults to true */
   showSaveAsDraft?: boolean;
}

const PropertiesTab: React.FC<PropertiesTabProps> = ({
   cultures = [],
   readonly = false,
   showArticleFields = false,
   showSaveAsDraft = true
}) => {
   return (
      <>
         <Form.Item
            label="Language"
            name="languageCode"
            rules={[
               {
                  max: 16,
                  message: "Language code must not exceed 16 characters"
               }
            ]}
         >
            <LanguageSelect
               cultures={cultures}
               placeholder="Select content language"
               allowClear
               disabled={readonly}
            />
         </Form.Item>

         <Form.Item
            label="Tags"
            name="tags"
            rules={[
               {
                  validator: validateTags,
                  validateTrigger: ["onChange", "onBlur"]
               }
            ]}
            normalize={(values: string[]) => values.map(normalizeTag)}
         >
            <Select
               mode="tags"
               placeholder="Add tags..."
               onKeyDown={(e: React.KeyboardEvent) => {
                  if (
                     e.key === "Space" &&
                     (e.target as HTMLInputElement).value === ""
                  ) {
                     e.preventDefault();
                  }
               }}
               tokenSeparators={[","]}
               disabled={readonly}
            />
         </Form.Item>

         {showArticleFields && showSaveAsDraft && (
            <Form.Item
               name="isDraft"
               valuePropName="checked"
               getValueFromEvent={(e) => e.target.checked}
            >
               <Checkbox disabled={readonly}>Save as draft</Checkbox>
            </Form.Item>
         )}
      </>
   );
};

export default PropertiesTab;
