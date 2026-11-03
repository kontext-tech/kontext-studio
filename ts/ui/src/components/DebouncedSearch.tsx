import { UI_TIMING } from "../constants/layout";
import { SearchOutlined } from "@kontext-labs/icons";
import { Input } from "antd";
import type { InputProps, InputRef } from "antd/es/input";
import { forwardRef, useEffect, useRef, useState } from "react";

export interface DebouncedSearchProps extends Omit<InputProps, "onChange"> {
   onSearch: (value: string) => void;
   defaultValue?: string;
   value?: string;
   delay?: number;
}

const DebouncedSearch = forwardRef<InputRef, DebouncedSearchProps>(
   (
      {
         onSearch,
         defaultValue = "",
         value: controlledValue,
         delay = UI_TIMING.SEARCH_DEBOUNCE_DELAY,
         ...inputProps
      },
      ref
   ) => {
      const [inputValue, setInputValue] = useState(
         controlledValue !== undefined ? controlledValue : defaultValue
      );
      const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
         null
      );

      useEffect(() => {
         if (controlledValue !== undefined && inputValue !== controlledValue) {
            setInputValue(controlledValue);
         }
      }, [controlledValue, inputValue]);

      const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
         const newValue = e.target.value;
         setInputValue(newValue);

         if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
         }

         searchTimeoutRef.current = setTimeout(() => {
            onSearch(newValue);
         }, delay);
      };

      useEffect(() => {
         return () => {
            if (searchTimeoutRef.current) {
               clearTimeout(searchTimeoutRef.current);
            }
         };
      }, []);

      return (
         <Input
            ref={ref}
            placeholder="Search..."
            allowClear
            value={inputValue}
            onChange={handleInputChange}
            prefix={<SearchOutlined />}
            {...inputProps}
            style={{ ...inputProps.style }}
         />
      );
   }
);

DebouncedSearch.displayName = "DebouncedSearch";

export default DebouncedSearch;
