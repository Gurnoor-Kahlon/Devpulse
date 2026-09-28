// Generated from FastAPI OpenAPI. Run npm run api:generate; do not edit.
export interface paths {
  "/health/live": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Check API process liveness
     * @description Return success when the API process can answer requests; no dependency checks.
     */
    get: operations["live_health_live_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/health/ready": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Check API readiness
     * @description Check startup and a bounded PostgreSQL query in the thread pool.
     */
    get: operations["ready_health_ready_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/csrf": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Csrf */
    get: operations["csrf_api_v1_auth_csrf_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/register": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Register */
    post: operations["register_api_v1_auth_register_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Login */
    post: operations["login_api_v1_auth_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/logout": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Logout */
    post: operations["logout_api_v1_auth_logout_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/me": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Me */
    get: operations["me_api_v1_auth_me_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/verify-email": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Verify Email */
    post: operations["verify_email_api_v1_auth_verify_email_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/resend-verification": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Resend */
    post: operations["resend_api_v1_auth_resend_verification_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/forgot-password": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Forgot */
    post: operations["forgot_api_v1_auth_forgot_password_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/reset-password": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Reset */
    post: operations["reset_api_v1_auth_reset_password_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/monitors": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Owned */
    get: operations["list_owned_api_v1_monitors_get"];
    put?: never;
    /** Create */
    post: operations["create_api_v1_monitors_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/monitors/{monitor_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get */
    get: operations["get_api_v1_monitors__monitor_id__get"];
    put?: never;
    post?: never;
    /** Archive */
    delete: operations["archive_api_v1_monitors__monitor_id__delete"];
    options?: never;
    head?: never;
    /** Update */
    patch: operations["update_api_v1_monitors__monitor_id__patch"];
    trace?: never;
  };
  "/api/v1/monitors/{monitor_id}/analytics": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Analytics */
    get: operations["analytics_api_v1_monitors__monitor_id__analytics_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/monitors/{monitor_id}/checks": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Checks */
    get: operations["checks_api_v1_monitors__monitor_id__checks_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/monitors/{monitor_id}/assertions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Assertions */
    get: operations["get_assertions_api_v1_monitors__monitor_id__assertions_get"];
    /** Put Assertions */
    put: operations["put_assertions_api_v1_monitors__monitor_id__assertions_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/incidents": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Owned */
    get: operations["list_owned_api_v1_incidents_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/incidents/{incident_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get */
    get: operations["get_api_v1_incidents__incident_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/dashboard": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get */
    get: operations["get_api_v1_dashboard_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/notifications/preferences": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Preferences */
    get: operations["preferences_api_v1_notifications_preferences_get"];
    /** Update Preferences */
    put: operations["update_preferences_api_v1_notifications_preferences_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/notifications/deliveries": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Deliveries */
    get: operations["deliveries_api_v1_notifications_deliveries_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /** AssertionDefinition */
    AssertionDefinition: {
      /**
       * Kind
       * @enum {string}
       */
      kind: "text_contains" | "json_equals";
      /**
       * Pointer
       * @default
       */
      pointer: string;
      /** Expected */
      expected: string | boolean | number | null;
    };
    /** AssertionPage */
    AssertionPage: {
      /**
       * Monitor Id
       * Format: uuid
       */
      monitor_id: string;
      /** Configuration Version */
      configuration_version: number;
      /**
       * Method
       * @enum {string}
       */
      method: "GET" | "HEAD";
      /** Items */
      items: components["schemas"]["AssertionSnapshot"][];
    };
    /** AssertionResult */
    AssertionResult: {
      definition: components["schemas"]["AssertionSnapshot"];
      /**
       * Status
       * @enum {string}
       */
      status: "passed" | "failed" | "not_evaluated";
      /**
       * Reason
       * @enum {string}
       */
      reason:
        | "matched"
        | "text_not_found"
        | "pointer_missing"
        | "value_mismatch"
        | "invalid_json"
        | "invalid_utf8"
        | "evaluation_limit"
        | "response_unavailable";
    };
    /** AssertionSnapshot */
    AssertionSnapshot: {
      /**
       * Kind
       * @enum {string}
       */
      kind: "text_contains" | "json_equals";
      /**
       * Pointer
       * @default
       */
      pointer: string;
      /** Expected */
      expected: string | boolean | number | null;
      /**
       * Id
       * Format: uuid
       */
      id: string;
    };
    /** AssertionUpdate */
    AssertionUpdate: {
      /** Configuration Version */
      configuration_version: number;
      /** Items */
      items: components["schemas"]["AssertionDefinition"][];
    };
    /** CheckEvidence */
    CheckEvidence: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      /**
       * Scheduled At
       * Format: date-time
       */
      scheduled_at: string;
      /** Configuration Version */
      configuration_version: number;
      /**
       * Trigger
       * @enum {string}
       */
      trigger: "manual" | "scheduled";
      /**
       * Run State
       * @enum {string}
       */
      run_state:
        | "pending"
        | "running"
        | "completed"
        | "cancelled"
        | "infrastructure_failed";
      /** Final Outcome */
      final_outcome: string | null;
      /** Attempt Number */
      attempt_number: number;
      /** Is Final Attempt */
      is_final_attempt: boolean;
      /**
       * Started At
       * Format: date-time
       */
      started_at: string;
      /**
       * Finished At
       * Format: date-time
       */
      finished_at: string;
      /**
       * Outcome
       * @enum {string}
       */
      outcome: "success" | "failure" | "blocked" | "infrastructure_failure";
      /** Http Status */
      http_status: number | null;
      /** Duration Ms */
      duration_ms: number;
      /** Error Code */
      error_code: string | null;
      /** Error Message */
      error_message: string | null;
      /**
       * Assertion Results
       * @default []
       */
      assertion_results: components["schemas"]["AssertionResult"][];
    };
    /** CheckPage */
    CheckPage: {
      /**
       * Start
       * Format: date-time
       */
      start: string;
      /**
       * End
       * Format: date-time
       */
      end: string;
      /** Items */
      items: components["schemas"]["CheckEvidence"][];
      /** Next Cursor */
      next_cursor: string | null;
    };
    /** CsrfResponse */
    CsrfResponse: {
      /** Csrf Token */
      csrf_token: string;
    };
    /** DashboardResponse */
    DashboardResponse: {
      /**
       * Window
       * @enum {string}
       */
      window: "24h" | "7d" | "30d";
      /**
       * Start
       * Format: date-time
       */
      start: string;
      /**
       * End
       * Format: date-time
       */
      end: string;
      /** Bucket Seconds */
      bucket_seconds: number;
      metrics: components["schemas"]["RunMetrics"];
      /** Buckets */
      buckets: components["schemas"]["TrendBucket"][];
      monitors: components["schemas"]["MonitorCounts"];
      /** Open Incidents */
      open_incidents: number;
      /** Recent Incidents */
      recent_incidents: components["schemas"]["IncidentResponse"][];
    };
    /** DeliveryPage */
    DeliveryPage: {
      /** Items */
      items: components["schemas"]["DeliveryResponse"][];
      /** Next Cursor */
      next_cursor: string | null;
    };
    /** DeliveryResponse */
    DeliveryResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Incident Id
       * Format: uuid
       */
      incident_id: string;
      /**
       * Transition
       * @enum {string}
       */
      transition: "opened" | "resolved";
      /**
       * Status
       * @enum {string}
       */
      status: "pending" | "sending" | "sent" | "failed" | "cancelled";
      /** Cancel Requested */
      cancel_requested: boolean;
      /** Attempt Count */
      attempt_count: number;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Next Attempt At */
      next_attempt_at: string | null;
      /** Completed At */
      completed_at: string | null;
      /** Last Error Code */
      last_error_code:
        | (
            | "smtp_unavailable"
            | "smtp_rejected"
            | "delivery_unknown"
            | "preferences_disabled"
            | "email_unverified"
          )
        | null;
    };
    /** EmailRequest */
    EmailRequest: {
      /**
       * Email
       * Format: email
       */
      email: string;
    };
    /** ErrorDetail */
    ErrorDetail: {
      /** Code */
      code: string;
      /** Message */
      message: string;
      /** Fields */
      fields?: components["schemas"]["FieldError"][] | null;
    };
    /** ErrorResponse */
    ErrorResponse: {
      error: components["schemas"]["ErrorDetail"];
      /** Request Id */
      request_id: string;
    };
    /** FieldError */
    FieldError: {
      /** Field */
      field: string;
      /** Code */
      code: string;
      /** Message */
      message: string;
    };
    /** HealthResponse */
    HealthResponse: {
      /**
       * Status
       * @default ok
       * @constant
       */
      status: "ok";
    };
    /** IncidentDetail */
    IncidentDetail: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Monitor Id
       * Format: uuid
       */
      monitor_id: string;
      /** Monitor Name */
      monitor_name: string;
      /**
       * Started At
       * Format: date-time
       */
      started_at: string;
      /**
       * Confirmed At
       * Format: date-time
       */
      confirmed_at: string;
      /** Resolved At */
      resolved_at: string | null;
      /** Opening Run Id */
      opening_run_id: string | null;
      /** Opening Check Id */
      opening_check_id: string | null;
      /** Confirmation Check Id */
      confirmation_check_id: string | null;
      /** Recovery Run Id */
      recovery_run_id: string | null;
      /** Recovery Check Id */
      recovery_check_id: string | null;
      opening_evidence: components["schemas"]["IncidentEvidence"];
      confirmation_evidence: components["schemas"]["IncidentEvidence"];
      recovery_evidence: components["schemas"]["IncidentEvidence"] | null;
      /**
       * Status
       * @enum {string}
       */
      readonly status: "open" | "resolved";
    };
    /** IncidentEvidence */
    IncidentEvidence: {
      /** Attempt Number */
      attempt_number: number;
      /** Configuration Version */
      configuration_version: number;
      /**
       * Method
       * @enum {string}
       */
      method: "GET" | "HEAD";
      /** Expected Status */
      expected_status: number;
      /**
       * Started At
       * Format: date-time
       */
      started_at: string;
      /**
       * Finished At
       * Format: date-time
       */
      finished_at: string;
      /**
       * Outcome
       * @enum {string}
       */
      outcome: "success" | "failure";
      /** Http Status */
      http_status: number | null;
      /** Duration Ms */
      duration_ms: number;
      /** Error Code */
      error_code: string | null;
      /** Error Message */
      error_message: string | null;
      /**
       * Assertion Results
       * @default []
       */
      assertion_results: components["schemas"]["AssertionResult"][];
    };
    /** IncidentPage */
    IncidentPage: {
      /** Items */
      items: components["schemas"]["IncidentResponse"][];
      /** Next Cursor */
      next_cursor: string | null;
    };
    /** IncidentResponse */
    IncidentResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Monitor Id
       * Format: uuid
       */
      monitor_id: string;
      /** Monitor Name */
      monitor_name: string;
      /**
       * Started At
       * Format: date-time
       */
      started_at: string;
      /**
       * Confirmed At
       * Format: date-time
       */
      confirmed_at: string;
      /** Resolved At */
      resolved_at: string | null;
      /**
       * Status
       * @enum {string}
       */
      readonly status: "open" | "resolved";
    };
    /** LoginRequest */
    LoginRequest: {
      /**
       * Email
       * Format: email
       */
      email: string;
      /**
       * Password
       * Format: password
       */
      password: string;
    };
    /** MessageResponse */
    MessageResponse: {
      /** Message */
      message: string;
    };
    /** MonitorAnalytics */
    MonitorAnalytics: {
      /**
       * Window
       * @enum {string}
       */
      window: "24h" | "7d" | "30d";
      /**
       * Start
       * Format: date-time
       */
      start: string;
      /**
       * End
       * Format: date-time
       */
      end: string;
      /** Bucket Seconds */
      bucket_seconds: number;
      metrics: components["schemas"]["RunMetrics"];
      /** Buckets */
      buckets: components["schemas"]["TrendBucket"][];
      monitor: components["schemas"]["MonitorResponse"];
      /** Archived At */
      archived_at: string | null;
      /** Status Distribution */
      status_distribution: components["schemas"]["StatusCount"][];
    };
    /** MonitorCounts */
    MonitorCounts: {
      /**
       * Total
       * @default 0
       */
      total: number;
      /**
       * Operational
       * @default 0
       */
      operational: number;
      /**
       * Down
       * @default 0
       */
      down: number;
      /**
       * Confirming Failure
       * @default 0
       */
      confirming_failure: number;
      /**
       * Unknown
       * @default 0
       */
      unknown: number;
      /**
       * Paused
       * @default 0
       */
      paused: number;
      /**
       * Stale
       * @default 0
       */
      stale: number;
      /**
       * Awaiting Check
       * @default 0
       */
      awaiting_check: number;
    };
    /** MonitorCreate */
    MonitorCreate: {
      /** Name */
      name: string;
      /** Url */
      url: string;
      /**
       * Method
       * @default GET
       * @enum {string}
       */
      method: "GET" | "HEAD";
      /**
       * Expected Status
       * @default 200
       */
      expected_status: number;
      /**
       * Interval Seconds
       * @default 60
       */
      interval_seconds: number;
      /**
       * Timeout Seconds
       * @default 5
       */
      timeout_seconds: number;
      /**
       * Enabled
       * @default true
       */
      enabled: boolean;
    };
    /** MonitorPage */
    MonitorPage: {
      /** Items */
      items: components["schemas"]["MonitorResponse"][];
      /** Next Cursor */
      next_cursor: string | null;
    };
    /** MonitorResponse */
    MonitorResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /** Url */
      url: string;
      /**
       * Method
       * @enum {string}
       */
      method: "GET" | "HEAD";
      /** Expected Status */
      expected_status: number;
      /** Interval Seconds */
      interval_seconds: number;
      /** Timeout Seconds */
      timeout_seconds: number;
      /** Enabled */
      enabled: boolean;
      /** Configuration Version */
      configuration_version: number;
      /** Next Due At */
      next_due_at: string | null;
      /**
       * Current State
       * @enum {string}
       */
      current_state: "unknown" | "operational" | "down" | "confirming_failure";
      /** Last Completed Check At */
      last_completed_check_at: string | null;
      /** Last Scheduled Check At */
      last_scheduled_check_at: string | null;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
      /**
       * Observation Status
       * @enum {string}
       */
      readonly observation_status:
        "paused" | "awaiting_check" | "current" | "stale";
    };
    /** MonitorUpdate */
    MonitorUpdate: {
      /** Configuration Version */
      configuration_version: number;
      /** Name */
      name?: string | null;
      /** Url */
      url?: string | null;
      /** Method */
      method?: ("GET" | "HEAD") | null;
      /** Expected Status */
      expected_status?: number | null;
      /** Interval Seconds */
      interval_seconds?: number | null;
      /** Timeout Seconds */
      timeout_seconds?: number | null;
      /** Enabled */
      enabled?: boolean | null;
    };
    /** NotificationPreferences */
    NotificationPreferences: {
      /** Configuration Version */
      configuration_version: number;
      /** Enabled */
      enabled: boolean;
      /** On Open */
      on_open: boolean;
      /** On Recovery */
      on_recovery: boolean;
      /** Destination */
      destination: string;
      /** Verified */
      verified: boolean;
    };
    /** NotificationUpdate */
    NotificationUpdate: {
      /** Configuration Version */
      configuration_version: number;
      /** Enabled */
      enabled: boolean;
      /** On Open */
      on_open: boolean;
      /** On Recovery */
      on_recovery: boolean;
    };
    /** RegisterRequest */
    RegisterRequest: {
      /**
       * Email
       * Format: email
       */
      email: string;
      /**
       * Password
       * Format: password
       */
      password: string;
    };
    /** ResetRequest */
    ResetRequest: {
      /**
       * Token
       * Format: password
       */
      token: string;
      /**
       * Password
       * Format: password
       */
      password: string;
    };
    /** RunMetrics */
    RunMetrics: {
      /** Successful Runs */
      successful_runs: number;
      /** Failed Runs */
      failed_runs: number;
      /** Observations */
      observations: number;
      /** Excluded Runs */
      excluded_runs: number;
      /** Uptime Percent */
      uptime_percent: number | null;
      /** Response Count */
      response_count: number;
      /** Mean Latency Ms */
      mean_latency_ms: number | null;
      /** First Observation At */
      first_observation_at: string | null;
      /** Last Observation At */
      last_observation_at: string | null;
    };
    /** StatusCount */
    StatusCount: {
      /** Http Status */
      http_status: number;
      /** Count */
      count: number;
      /** Percentage */
      percentage: number;
    };
    /** TokenRequest */
    TokenRequest: {
      /**
       * Token
       * Format: password
       */
      token: string;
    };
    /** TrendBucket */
    TrendBucket: {
      /** Successful Runs */
      successful_runs: number;
      /** Failed Runs */
      failed_runs: number;
      /** Observations */
      observations: number;
      /** Excluded Runs */
      excluded_runs: number;
      /** Uptime Percent */
      uptime_percent: number | null;
      /** Response Count */
      response_count: number;
      /** Mean Latency Ms */
      mean_latency_ms: number | null;
      /** First Observation At */
      first_observation_at: string | null;
      /** Last Observation At */
      last_observation_at: string | null;
      /**
       * Start
       * Format: date-time
       */
      start: string;
      /**
       * End
       * Format: date-time
       */
      end: string;
      /** Partial */
      partial: boolean;
    };
    /** UserResponse */
    UserResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Email */
      email: string;
      /** Email Verified At */
      email_verified_at: string | null;
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  live_health_live_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HealthResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  ready_health_ready_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HealthResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Startup or PostgreSQL is unavailable. */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  csrf_api_v1_auth_csrf_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CsrfResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_api_v1_auth_register_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MessageResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  login_api_v1_auth_login_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LoginRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  logout_api_v1_auth_logout_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MessageResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  me_api_v1_auth_me_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  verify_email_api_v1_auth_verify_email_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TokenRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MessageResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  resend_api_v1_auth_resend_verification_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EmailRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MessageResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  forgot_api_v1_auth_forgot_password_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EmailRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MessageResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  reset_api_v1_auth_reset_password_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ResetRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MessageResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_owned_api_v1_monitors_get: {
    parameters: {
      query?: {
        limit?: number;
        cursor?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MonitorPage"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  create_api_v1_monitors_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["MonitorCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MonitorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_api_v1_monitors__monitor_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        monitor_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MonitorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  archive_api_v1_monitors__monitor_id__delete: {
    parameters: {
      query: {
        configuration_version: number;
      };
      header?: never;
      path: {
        monitor_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_api_v1_monitors__monitor_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        monitor_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["MonitorUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MonitorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  analytics_api_v1_monitors__monitor_id__analytics_get: {
    parameters: {
      query?: {
        window?: "24h" | "7d" | "30d";
      };
      header?: never;
      path: {
        monitor_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MonitorAnalytics"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  checks_api_v1_monitors__monitor_id__checks_get: {
    parameters: {
      query?: {
        window?: "24h" | "7d" | "30d";
        limit?: number;
        cursor?: string | null;
      };
      header?: never;
      path: {
        monitor_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CheckPage"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_assertions_api_v1_monitors__monitor_id__assertions_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        monitor_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AssertionPage"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  put_assertions_api_v1_monitors__monitor_id__assertions_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        monitor_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AssertionUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AssertionPage"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_owned_api_v1_incidents_get: {
    parameters: {
      query?: {
        limit?: number;
        cursor?: string | null;
        status?: ("open" | "resolved") | null;
        monitor_id?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["IncidentPage"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_api_v1_incidents__incident_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        incident_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["IncidentDetail"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_api_v1_dashboard_get: {
    parameters: {
      query?: {
        window?: "24h" | "7d" | "30d";
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DashboardResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  preferences_api_v1_notifications_preferences_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["NotificationPreferences"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_preferences_api_v1_notifications_preferences_put: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["NotificationUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["NotificationPreferences"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  deliveries_api_v1_notifications_deliveries_get: {
    parameters: {
      query?: {
        limit?: number;
        cursor?: string | null;
        incident_id?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DeliveryPage"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Invalid request values. */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unexpected internal error. */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
}
