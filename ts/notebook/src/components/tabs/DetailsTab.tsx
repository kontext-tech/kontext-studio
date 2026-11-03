import { Form, Input } from "antd";
import React from "react";

interface DetailsTabProps {
   readonly?: boolean;
   showArticleFields?: boolean;
}

const DetailsTab: React.FC<DetailsTabProps> = ({
   readonly = false,
   showArticleFields = false
}) => {
   return (
      <>
         <Form.Item
            label="Description"
            name="description"
            rules={[
               {
                  max: 1000,
                  message: "Description must not exceed 1000 characters"
               }
            ]}
         >
            <Input.TextArea
               placeholder="Brief description of the notebook"
               autoSize={{ minRows: 3, maxRows: 6 }}
               showCount
               maxLength={1000}
               disabled={readonly}
            />
         </Form.Item>

         {showArticleFields && (
            <Form.Item
               label="Keywords"
               name="keyWords"
               rules={[
                  {
                     max: 128,
                     message: "Keywords must not exceed 128 characters"
                  }
               ]}
            >
               <Input
                  placeholder="keyword1, keyword2, keyword3"
                  disabled={readonly}
               />
            </Form.Item>
         )}
      </>
   );
};

export default DetailsTab;
