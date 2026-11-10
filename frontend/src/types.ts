export type User = {
  id: string;
  username: string;
  role: "admin" | "operator";
  active: boolean;
};
export type Session = { user: User; csrf_token: string };
export type PlatformField = {
  key: string;
  label: string;
  field_type: "text" | "email" | "integer" | "select";
  required: boolean;
  options: string[];
};
export type Platform = {
  id: string;
  name: string;
  description: string;
  active: boolean;
  mode: "simulation" | "power_automate" | "local_browser" | "local_desktop";
  fields: PlatformField[];
  config: { simulate_failure: boolean };
};
export type Action =
  | "open_page"
  | "locate"
  | "fill"
  | "click"
  | "click_point"
  | "assert"
  | "click_image"
  | "click_button"
  | "assert_image";
export type FlowAction = Action | "wait_image" | "if_exists" | "pause";
export type Step = {
  action: FlowAction;
  locator: string;
  value: string;
  data_ref: string;
  timeout_seconds: number;
  success_condition: string;
  screen_context: {
    x: number;
    y: number;
    width: number;
    height: number;
    window: string;
  } | null;
  button_text: string;
  reference_image_id: string | null;
  confidence: number;
  on_match?: "finish_success" | "skip_next" | "continue";
  skip_steps?: number;
};
export type Automation = {
  id: string;
  name: string;
  version: number;
  status: string;
  steps: (Step & { position: number })[];
};
export type Employee = {
  name: string;
  email: string;
  department: string;
  employee_id: string;
};
export type Execution = {
  id: string;
  platform_name: string;
  platform_id: string;
  status: string;
  mode: string;
  attempts: number;
  error_code: string | null;
  can_retry: boolean;
  result: {
    code?: string;
    artifact_id?: string;
    failed_step?: number;
    action?: string;
    schematic?: boolean;
  };
  awaiting_operator?: boolean;
  cancel_requested?: boolean;
  created_at: string;
};
export type ProvisioningRequest = {
  id: string;
  employee: Employee;
  status: string;
  executions: Execution[];
  created_at: string;
  requested_by: string;
};
export type ExecutionEvent = {
  id: string;
  sequence: number;
  step: number | null;
  level: string;
  message: string;
  created_at: string;
};
export type AuditEvent = {
  id: string;
  actor_id: string | null;
  action: string;
  resource_id: string;
  details: Record<string, unknown>;
  created_at: string;
};
export type StepTest = {
  id: string;
  status: string;
  mode: string;
  preview_only: boolean;
  result: {
    code?: string;
    message?: string;
    simulated?: boolean;
    target?: { x: number; y: number; width: number; height: number };
    artifact_id?: string;
  };
  error_code: string | null;
};
export const statusLabels: Record<string, string> = {
  queued: "Na fila",
  dispatching: "Enviando",
  running: "Em andamento",
  succeeded: "Concluída",
  partially_succeeded: "Parcial",
  failed: "Falhou",
  cancelled: "Cancelada",
  draft: "Rascunho",
  validated: "Validada",
  archived: "Arquivada",
};
export function formatDate(value: string) {
  return new Date(
    /[Z+]|-\d\d:\d\d$/.test(value) ? value : value + "Z",
  ).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}
export function message(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Não foi possível concluir a operação.";
}
