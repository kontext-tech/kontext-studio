import { useRoute } from "@/hooks/useRoute";
import { AppFooter, AuthCardLayout } from "@kontext-labs/layout";

const AuthLayout: React.FC = () => {
   const { currentRoute } = useRoute();

   const isFullWidth = currentRoute?.fullWidth === true;

   return (
      <AuthCardLayout
         isFullWidth={isFullWidth}
         logoAlt="Kontext"
         footer={<AppFooter showDetails={true} />}
      />
   );
};

export default AuthLayout;
