import { apiGet } from "./client";

export interface HealthResponse {
  status: "ok";
  app_name: string;
  version: string;
  environment: string;
}

export function getHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/health");
}
