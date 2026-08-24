import axios from "axios";
import type {
  ApiEnvelope, ScheduleResult, Machine, Operator, OrderSummary, DashboardData,
  DisruptionRecord, StrategyComparisonData, CostBreakdown, ScheduleMetrics, Strategy,
} from "../types";

// Never hardcode localhost in production code - read from the environment
// (Section 36). Falls back to localhost only for local development.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000, // schedule generation can legitimately take up to ~90s
});

function unwrap<T>(promise: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
  return promise.then((res) => {
    if (!res.data.success) {
      const err = new Error(res.data.error || "Request failed") as Error & { suggestion?: string };
      err.suggestion = res.data.suggestion;
      throw err;
    }
    return res.data.data as T;
  });
}

export const scheduleApi = {
  get: (strategy: Strategy = "cheapest") =>
    unwrap<ScheduleResult>(api.get(`/api/schedule`, { params: { strategy } })),
  generate: (strategy: Strategy = "cheapest", timeLimitSeconds = 60, regenerateData = false) =>
    unwrap<ScheduleResult>(api.post(`/api/schedule/generate`, {
      strategy, time_limit_seconds: timeLimitSeconds, regenerate_data: regenerateData,
    })),
  replan: (disruptionType: string, payload: Record<string, unknown>, strategy: Strategy = "cheapest") =>
    unwrap<ScheduleResult>(api.post(`/api/schedule/replan`, {
      disruption_type: disruptionType, payload, strategy,
    })),
};

export const orderApi = {
  list: (strategy: Strategy = "cheapest") =>
    unwrap<OrderSummary[]>(api.get(`/api/orders`, { params: { strategy } })),
};

export const machineApi = {
  list: (strategy: Strategy = "cheapest") =>
    unwrap<Machine[]>(api.get(`/api/machines`, { params: { strategy } })),
};

export const operatorApi = {
  list: () => unwrap<Operator[]>(api.get(`/api/operators`)),
};

export const dashboardApi = {
  get: (strategy: Strategy = "cheapest") =>
    unwrap<DashboardData>(api.get(`/api/dashboard`, { params: { strategy } })),
};

export const costApi = {
  get: (strategy: Strategy = "cheapest") =>
    unwrap<CostBreakdown>(api.get(`/api/costs`, { params: { strategy } })),
};

export const metricsApi = {
  get: (strategy: Strategy = "cheapest") =>
    unwrap<ScheduleMetrics>(api.get(`/api/metrics`, { params: { strategy } })),
};

export const disruptionApi = {
  list: () => unwrap<DisruptionRecord[]>(api.get(`/api/disruptions`)),
  breakdown: (payload: Record<string, unknown>) =>
    unwrap<ScheduleResult>(api.post(`/api/disruptions/breakdown`, payload)),
  operatorAbsence: (payload: Record<string, unknown>) =>
    unwrap<ScheduleResult>(api.post(`/api/disruptions/operator-absence`, payload)),
  materialDelay: (payload: Record<string, unknown>) =>
    unwrap<ScheduleResult>(api.post(`/api/disruptions/material-delay`, payload)),
  rework: (payload: Record<string, unknown>) =>
    unwrap<ScheduleResult>(api.post(`/api/disruptions/rework`, payload)),
  powerCut: (payload: Record<string, unknown>) =>
    unwrap<ScheduleResult>(api.post(`/api/disruptions/power-cut`, payload)),
};

export const strategyApi = {
  list: () => unwrap<Array<{ strategy: Strategy; description: string }>>(api.get(`/api/strategies`)),
  compare: (timeLimitSeconds = 45) =>
    unwrap<StrategyComparisonData>(api.post(`/api/strategies/compare`, { time_limit_seconds: timeLimitSeconds })),
};
