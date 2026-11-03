import type {
   CatalogConnection,
   CatalogConnectionAuthType,
   CatalogConnectionRequest,
   CatalogExecutionMode,
   CatalogProviderDefinition
} from "@kontext-labs/schema";

export type CatalogFormValues = {
   providerKind: string;
   displayName: string;
   description?: string;
   enabled: boolean;
   authType?: CatalogConnectionAuthType;
   executionMode?: CatalogExecutionMode;
   defaultNamespace?: string;
   host?: string;
   port?: number;
   databaseName?: string;
   username?: string;
   databasePath?: string;
   serviceName?: string;
   instanceName?: string;
   secretRef?: string;
   secretValue?: string;
};

export type ConfigFieldDefinition = {
   name: keyof CatalogFormValues;
   label: string;
   required?: boolean;
   type?: "text" | "number" | "password";
   placeholder?: string;
   columnSpan?: number;
};

type ProviderFormRegistryEntry = {
   defaults: Partial<CatalogFormValues>;
   fields: ConfigFieldDefinition[];
   configOptions?: Record<string, string>;
};

const PROVIDER_FORM_REGISTRY: Record<string, ProviderFormRegistryEntry> = {
   duckdb_external: {
      defaults: {
         databasePath: "",
         defaultNamespace: "main"
      },
      fields: [
         {
            name: "databasePath",
            label: "Database Path",
            required: true,
            placeholder: "/path/to/database.duckdb"
         },
         {
            name: "defaultNamespace",
            label: "Default Namespace",
            placeholder: "main",
            columnSpan: 12
         }
      ]
   },
   mysql_external: {
      defaults: {
         host: "localhost",
         port: 3306,
         databaseName: "mysql",
         username: "root",
         defaultNamespace: "default"
      },
      fields: [
         {
            name: "host",
            label: "Host",
            required: true,
            placeholder: "localhost",
            columnSpan: 12
         },
         {
            name: "port",
            label: "Port",
            type: "number",
            placeholder: "3306",
            columnSpan: 12
         },
         {
            name: "databaseName",
            label: "Database",
            required: true,
            placeholder: "mysql",
            columnSpan: 12
         },
         {
            name: "username",
            label: "Username",
            placeholder: "root",
            columnSpan: 12
         },
         {
            name: "defaultNamespace",
            label: "Default Namespace",
            placeholder: "default",
            columnSpan: 12
         }
      ]
   },
   oracle_external: {
      defaults: {
         host: "localhost",
         port: 1521,
         username: "system",
         serviceName: "FREEPDB1",
         defaultNamespace: "SYSTEM"
      },
      fields: [
         {
            name: "host",
            label: "Host",
            required: true,
            placeholder: "localhost",
            columnSpan: 12
         },
         {
            name: "port",
            label: "Port",
            type: "number",
            placeholder: "1521",
            columnSpan: 12
         },
         {
            name: "serviceName",
            label: "Service Name",
            required: true,
            placeholder: "FREEPDB1",
            columnSpan: 12
         },
         {
            name: "username",
            label: "Username",
            placeholder: "system",
            columnSpan: 12
         },
         {
            name: "defaultNamespace",
            label: "Default Namespace",
            placeholder: "SYSTEM",
            columnSpan: 12
         }
      ]
   },
   postgresql_external: {
      defaults: {
         host: "localhost",
         port: 5432,
         databaseName: "postgres",
         username: "postgres",
         defaultNamespace: "public"
      },
      fields: [
         {
            name: "host",
            label: "Host",
            required: true,
            placeholder: "localhost",
            columnSpan: 12
         },
         {
            name: "port",
            label: "Port",
            type: "number",
            placeholder: "5432",
            columnSpan: 12
         },
         {
            name: "databaseName",
            label: "Database",
            required: true,
            placeholder: "postgres",
            columnSpan: 12
         },
         {
            name: "username",
            label: "Username",
            placeholder: "postgres",
            columnSpan: 12
         },
         {
            name: "defaultNamespace",
            label: "Default Namespace",
            placeholder: "public",
            columnSpan: 12
         }
      ]
   },
   sqlserver_external: {
      defaults: {
         host: "localhost",
         port: 1433,
         databaseName: "master",
         username: "sa",
         instanceName: "",
         defaultNamespace: "dbo"
      },
      configOptions: {
         driver: "ODBC Driver 18 for SQL Server",
         encrypt: "yes",
         trustServerCertificate: "yes"
      },
      fields: [
         {
            name: "host",
            label: "Host",
            required: true,
            placeholder: "localhost",
            columnSpan: 12
         },
         {
            name: "port",
            label: "Port",
            type: "number",
            placeholder: "1433",
            columnSpan: 12
         },
         {
            name: "databaseName",
            label: "Database",
            required: true,
            placeholder: "master",
            columnSpan: 12
         },
         {
            name: "username",
            label: "Username",
            placeholder: "sa",
            columnSpan: 12
         },
         {
            name: "instanceName",
            label: "Instance Name",
            placeholder: "SQLEXPRESS",
            columnSpan: 12
         },
         {
            name: "defaultNamespace",
            label: "Default Namespace",
            placeholder: "dbo",
            columnSpan: 12
         }
      ]
   },
   sqlite_external: {
      defaults: {
         databasePath: "",
         defaultNamespace: "main"
      },
      fields: [
         {
            name: "databasePath",
            label: "Database Path",
            required: true,
            placeholder: "/path/to/database.db"
         },
         {
            name: "defaultNamespace",
            label: "Default Namespace",
            placeholder: "main",
            columnSpan: 12
         }
      ]
   },
   teradata_external: {
      defaults: {
         host: "localhost",
         port: 1025,
         databaseName: "dbc",
         username: "dbc",
         defaultNamespace: "dbc"
      },
      configOptions: {
         logmech: "TD2"
      },
      fields: [
         {
            name: "host",
            label: "Host",
            required: true,
            placeholder: "localhost",
            columnSpan: 12
         },
         {
            name: "port",
            label: "Port",
            type: "number",
            placeholder: "1025",
            columnSpan: 12
         },
         {
            name: "databaseName",
            label: "Database",
            required: true,
            placeholder: "dbc",
            columnSpan: 12
         },
         {
            name: "username",
            label: "Username",
            placeholder: "dbc",
            columnSpan: 12
         },
         {
            name: "defaultNamespace",
            label: "Default Namespace",
            placeholder: "dbc",
            columnSpan: 12
         }
      ]
   }
};

const getProviderRegistryEntry = (providerKind?: string) =>
   providerKind ? PROVIDER_FORM_REGISTRY[providerKind] : undefined;

const EXECUTION_MODE_LABELS: Record<string, string> = {
   duckdb_federated: "DuckDB federation",
   native_pushdown: "Native pushdown",
   materialized: "Materialized"
};

export const getProviderFields = (providerKind?: string) =>
   getProviderRegistryEntry(providerKind)?.fields || [];

export const getExecutionModeLabel = (executionMode?: string | null) =>
   EXECUTION_MODE_LABELS[executionMode ?? ""] ||
   executionMode?.split("_").join(" ") ||
   null;

export const getAuthTypeLabel = (authType?: CatalogConnectionAuthType) => {
   if (!authType) {
      return "Default";
   }

   return authType === "secret_ref" ? "Secret" : authType;
};

export const getFormValues = (
   provider: CatalogProviderDefinition | undefined,
   connection?: CatalogConnection | null
): CatalogFormValues => {
   const defaults =
      getProviderRegistryEntry(provider?.providerKind)?.defaults || {};
   const config = connection?.config;

   return {
      providerKind: connection?.providerKind || provider?.providerKind || "",
      displayName: connection?.displayName || provider?.displayName || "",
      description: connection?.description || undefined,
      enabled: connection?.enabled ?? true,
      authType: connection?.authType || provider?.authTypes[0] || undefined,
      executionMode:
         connection?.executionMode || provider?.executionModes[0] || undefined,
      host: config?.host || defaults.host || undefined,
      port: config?.port || defaults.port || undefined,
      databaseName: config?.databaseName || defaults.databaseName || undefined,
      username: config?.username || defaults.username || undefined,
      databasePath: config?.databasePath || defaults.databasePath || undefined,
      serviceName: config?.serviceName || defaults.serviceName || undefined,
      instanceName: config?.instanceName || defaults.instanceName || undefined,
      defaultNamespace:
         config?.defaultNamespace || defaults.defaultNamespace || undefined,
      secretRef: connection?.secretRef || undefined,
      secretValue: undefined
   };
};

export const buildConnectionRequest = (
   values: CatalogFormValues,
   provider: CatalogProviderDefinition
): CatalogConnectionRequest => {
   const registryEntry = getProviderRegistryEntry(provider.providerKind);
   const config = {
      host: values.host || undefined,
      port: values.port ?? undefined,
      databaseName: values.databaseName || undefined,
      username: values.username || undefined,
      databasePath: values.databasePath || undefined,
      serviceName: values.serviceName || undefined,
      instanceName: values.instanceName || undefined,
      defaultNamespace: values.defaultNamespace || undefined,
      options: registryEntry?.configOptions || {}
   };

   return {
      providerKind: provider.providerKind,
      connectionKind: provider.connectionKind,
      displayName: values.displayName.trim(),
      description: values.description?.trim() || undefined,
      enabled: values.enabled,
      sourceCategory: provider.sourceCategory,
      authType: values.authType || provider.authTypes[0] || undefined,
      executionMode:
         values.executionMode || provider.executionModes[0] || undefined,
      config,
      secretRef: values.secretRef?.trim() || undefined,
      secretValue: values.secretValue?.trim() || undefined,
      capabilities: provider.capabilities
   };
};
