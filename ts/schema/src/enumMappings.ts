/**
 * Enum Numeric Value Mappings
 * Source of truth: backend/Kontext.Data/Primitives.cs
 *
 * Maps all enum names to their actual database numeric values.
 * Important: These numbers must match the database storage format.
 *
 * Note: Some enums like JobParameterType, JobCategory, JobExecutionRuntime,
 * and TokenPurpose use sequential values starting from 0.
 */

export const EnumNumericMappings: Record<string, Record<string, number>> = {
   // Sequential enums (0, 1, 2, ...)
   FileFormatType: {
      Default: 0,
      Markdown: 1,
      Image: 2,
      DrawIO: 3,
      CSV: 4,
      PDF: 5,
      Parquet: 6,
      Text: 7,
      JSON: 8,
      JSONL: 9,
      TSV: 10,
      Notebook: 11,
      Chart: 12,
      DataTable: 13,
      Excel: 14
   },

   ProjectFeature: {
      Documentation: 0,
      DataLake: 1,
      Search: 2,
      Chat: 3
   },

   AccessLevel: {
      Private: 0,
      Public: 1
   },

   ChannelType: {
      Other: 0,
      Web: 1,
      Mobile: 2,
      Api: 3
   },

   NotificationType: {
      Default: 0,
      NewComment: 1,
      Like: 2
   },

   SortBy: {
      Default: 0,
      Latest: 1,
      Creation: 2,
      Views: 3,
      Likes: 4,
      Modified: 5,
      Name: 6,
      Title: 7,
      Rating: 8,
      Popularity: 9
   },

   JobRunSortBy: {
      DateCreated: 0,
      StartedAt: 1,
      CompletedAt: 2,
      Duration: 3,
      Status: 4,
      JobName: 5
   },

   JobSortBy: {
      DateCreated: 0,
      Name: 1,
      DateModified: 2,
      Type: 3,
      LastRunDate: 4
   },

   UserType: {
      User: 0,
      ServiceAccount: 1
   },

   JobRunStatus: {
      Queued: 0,
      Dispatched: 1,
      Running: 2,
      Succeeded: 3,
      Failed: 4,
      Canceled: 5,
      TimedOut: 6,
      DeadLettered: 7
   },

   JobRetryStrategy: {
      None: 0,
      Immediate: 1,
      Linear: 2,
      Exponential: 3,
      Fixed: 4
   },

   JobTriggerType: {
      Scheduled: 0,
      Event: 1,
      Manual: 2,
      Dependency: 3,
      Retry: 4,
      Interactive: 5
   },

   LogLevel: {
      Trace: 0,
      Debug: 1,
      Information: 2,
      Warning: 3,
      Error: 4,
      Critical: 5,
      None: 6
   },

   CampaignStatus: {
      Created: 0,
      DeliveryListGeneration: 1,
      DeliveryListGenerated: 2,
      DeliveryInProgress: 3,
      DeliveryCompleted: 4
   },

   JobParameterType: {
      String: 0,
      Integer: 1,
      Boolean: 2
   },

   JobCategory: {
      General: 0,
      DataManagement: 1,
      ContentManagement: 2,
      SystemMaintenance: 3,
      Import: 4,
      Export: 5,
      Notification: 6,
      Cleanup: 7,
      Analytics: 8,
      Security: 9,
      Maintenance: 10,
      Processing: 11,
      DataProcessing: 12
   },

   JobExecutionRuntime: {
      DotNet: 0,
      Python: 1
   },

   TokenPurpose: {
      EmailUnsubscribe: 0,
      InvitationCode: 1,
      AccountRegister: 2,
      EmailVerification: 3,
      PasswordReset: 4
   },

   // AI & Chat enums (not in Kontext.Data yet, but use 0-based convention)
   ToolCallStatus: {
      started: 0,
      completed: 1,
      error: 2
   },

   RunEvent: {
      RunStarted: 0,
      RunContent: 1,
      RunIntermediateContent: 2,
      RunCompleted: 3,
      RunError: 4,
      RunCancelled: 5,
      RunPaused: 6,
      RunContinued: 7,
      ToolCallStarted: 8,
      ToolCallCompleted: 9,
      ReasoningStarted: 10,
      ReasoningStep: 11,
      ReasoningCompleted: 12,
      MemoryUpdateStarted: 13,
      MemoryUpdateCompleted: 14,
      ParserModelResponseStarted: 15,
      ParserModelResponseCompleted: 16,
      OutputModelResponseStarted: 17,
      OutputModelResponseCompleted: 18,
      ArtifactEvent: 19,
      WorkflowEvent: 20,
      CustomEvent: 21
   },

   ArtifactType: {
      DataTable: 0,
      Notebook: 1,
      Chart: 2
   },

   ChatMessageType: {
      user: 0,
      assistant: 1,
      system: 2
   },

   ChatMessageStatus: {
      loading: 0,
      streaming: 1,
      completed: 2,
      error: 3
   },

   ChatMessageSegmentType: {
      text: 0,
      tool_call: 1,
      error: 2,
      artifact: 3,
      object: 4,
      reasoning: 5
   },

   ColumnDataType: {
      TinyInt: 0,
      SmallInt: 1,
      Integer: 2,
      BigInt: 3,
      HugeInt: 4,
      UTinyInt: 5,
      USmallInt: 6,
      UInteger: 7,
      UBigInt: 8,
      UHugeInt: 9,
      Real: 10,
      Float: 11,
      Double: 12,
      Decimal: 13,
      Numeric: 14,
      VarChar: 15,
      Char: 16,
      Text: 17,
      String: 18,
      Blob: 19,
      Bytea: 20,
      VarBinary: 21,
      Binary: 22,
      Date: 23,
      Time: 24,
      TimeTz: 25,
      Timestamp: 26,
      TimestampTz: 27,
      TimestampS: 28,
      TimestampMs: 29,
      TimestampNs: 30,
      Interval: 31,
      Boolean: 32,
      Bool: 33,
      Uuid: 34,
      Json: 35,
      Array: 36,
      List: 37,
      Struct: 38,
      Row: 39,
      Map: 40,
      Union: 41,
      Enum: 42,
      Bit: 43,
      BitString: 44,
      Nested: 45,
      AggregateState: 46,
      Null: 47,
      Any: 48,
      Unknown: 49
   },

   DualAxesChartType: {
      Interval: 0,
      line: 1,
      area: 2
   },

   ProblemTypes: {
      RequiresTwoFactor: 0,
      InvalidCredentials: 1,
      ResourceNotFound: 2,
      Unauthorized: 3,
      AccountNotActivated: 4,
      ValidationFailed: 5,
      Timeout: 6,
      UnexpectedError: 7,
      InvalidCaptcha: 8,
      MissingCaptcha: 9,
      InvalidCaptchaContext: 10,
      UnsupportedTokenVersion: 11
   },

   ColorPalette: {
      category10: 0,
      accent: 1,
      dark2: 2,
      paired: 3,
      pastel1: 4,
      pastel2: 5,
      set1: 6,
      set2: 7,
      set3: 8,
      tableau10: 9,
      blues: 10,
      brBG: 11,
      buGn: 12,
      buPu: 13,
      cividis: 14,
      cool: 15,
      cubehelixDefault: 16,
      gnBu: 17,
      greens: 18,
      greys: 19,
      inferno: 20,
      magma: 21,
      oranges: 22,
      orRd: 23,
      piYG: 24,
      plasma: 25,
      pRGn: 26,
      puBu: 27,
      puBuGn: 28,
      puOr: 29,
      puRd: 30,
      purples: 31,
      rainbow: 32,
      rdBu: 33,
      rdGy: 34,
      rdPu: 35,
      rdYlBu: 36,
      rdYlGn: 37,
      reds: 38,
      sinebow: 39,
      spectral: 40,
      turbo: 41,
      viridis: 42,
      warm: 43,
      ylGn: 44,
      ylGnBu: 45,
      ylOrBr: 46,
      ylOrRd: 47
   },

   MarkTypes: {
      auto: 0,
      interval: 1,
      rect: 2,
      line: 3,
      point: 4,
      text: 5,
      cell: 6,
      area: 7,
      node: 8,
      edge: 9,
      link: 10,
      image: 11,
      polygon: 12,
      box: 13,
      vector: 14,
      lineX: 15,
      lineY: 16,
      connector: 17,
      range: 18,
      rangeX: 19,
      rangeY: 20,
      sankey: 21,
      chord: 22,
      path: 23,
      treemap: 24,
      pack: 25,
      boxplot: 26,
      shape: 27,
      forceGraph: 28,
      tree: 29,
      wordCloud: 30,
      gauge: 31,
      density: 32,
      heatmap: 33,
      liquid: 34
   },

   // Non-sequential enum (gaps due to deleted values)
   EventType: {
      Other: 0,
      CreateProject: 9,
      ModifyProject: 10,
      ViewProject: 18,
      ViewPage: 20,
      Login: 17,
      Register: 30,
      ConfirmEmail: 44,
      EditProfile: 24,
      ChangePassword: 25,
      Enable2FA: 26,
      Disable2FA: 27,
      EnableUser: 28,
      DisableUser: 29,
      CreateServiceAccount: 31,
      EnableServiceAccount: 32,
      DisableServiceAccount: 33,
      AuthenticateServiceAccount: 34,
      CreateServiceAccountKey: 35,
      EnableServiceAccountKey: 36,
      DisableServiceAccountKey: 37,
      DeleteServiceAccountKey: 38,
      CreateFile: 39,
      CreateFiles: 40,
      DeleteFile: 41,
      UpdateFileSchema: 43,
      ProcessFailedEvent: 42,
      CreateCatalogEntity: 48,
      UpdateCatalogEntity: 49,
      DeleteCatalogEntity: 50,
      SubscribeToGroup: 51,
      UnsubscribeFromGroup: 52,
      RequestCampaignEmailDelivery: 53,
      SessionRefresh: 54
   }
};

/**
 * Get numeric value for an enum value
 */
export function getEnumNumericValue(
   enumName: string,
   enumValue: string
): number | undefined {
   return EnumNumericMappings[enumName]?.[enumValue];
}

/**
 * Get all enums with their numeric mappings
 */
export function getAllEnumMappings(): Record<string, Record<string, number>> {
   return EnumNumericMappings;
}
