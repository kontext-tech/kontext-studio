import type { CultureInfoModel } from "@kontext-labs/schema";
import { Select } from "antd";
import type { SelectProps } from "antd/es/select";

interface LanguageSelectProps extends Omit<
   SelectProps,
   "options" | "onChange" | "value"
> {
   value?: string;
   onChange?: (value: string) => void;
   cultures?: CultureInfoModel[];
   placeholder?: string;
   loading?: boolean;
}

const LanguageSelect = ({
   value,
   onChange,
   cultures = [],
   placeholder = "Select language",
   loading = false,
   ...selectProps
}: LanguageSelectProps) => {
   return (
      <Select
         value={value}
         onChange={onChange}
         placeholder={placeholder}
         loading={loading}
         options={cultures.map((c) => ({
            label: c.nativeName,
            value: c.code
         }))}
         {...selectProps}
      />
   );
};

export default LanguageSelect;
