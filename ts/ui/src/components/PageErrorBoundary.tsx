import { Alert, Button, Result, Typography } from "antd";
import { Component, type ErrorInfo, type ReactNode } from "react";

const { Paragraph, Text } = Typography;

interface Props {
   children: ReactNode;
}

interface State {
   hasError: boolean;
   error: Error | null;
   errorInfo: ErrorInfo | null;
}

class PageErrorBoundary extends Component<Props, State> {
   public state: State = {
      hasError: false,
      error: null,
      errorInfo: null
   };

   public static getDerivedStateFromError(error: Error): State {
      return { hasError: true, error, errorInfo: null };
   }

   public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
      this.setState({
         error,
         errorInfo
      });
      console.error("Uncaught error:", error, errorInfo);
   }

   private handleReload = () => {
      window.location.reload();
   };

   public render() {
      if (this.state.hasError) {
         return (
            <div
               style={{ padding: "40px", maxWidth: "800px", margin: "0 auto" }}
            >
               <Result
                  status="error"
                  title="Something went wrong"
                  subTitle="An unexpected error occurred. Try reloading the page."
                  extra={[
                     <Button
                        type="primary"
                        key="reload"
                        onClick={this.handleReload}
                     >
                        Reload Page
                     </Button>,
                     <Button key="back" onClick={() => window.history.back()}>
                        Go Back
                     </Button>
                  ]}
               >
                  <div className="desc">
                     <Paragraph>
                        <Text strong style={{ fontSize: 16 }}>
                           Technical Details:
                        </Text>
                     </Paragraph>
                     <Alert
                        title={this.state.error?.message || "Unknown error"}
                        type="error"
                        showIcon
                        banner
                        style={{ marginBottom: "16px" }}
                     />
                     <Paragraph>
                        <Text type="secondary">
                           If the problem persists, please contact support with
                           the details provided above.
                        </Text>
                     </Paragraph>
                  </div>
               </Result>
            </div>
         );
      }

      return this.props.children;
   }
}

export default PageErrorBoundary;
