export type Strategy = "cheapest" | "most_on_time" | "most_robust";

export type OrderStatus = "ON_TRACK" | "AT_RISK" | "LATE" | "UNSCHEDULED";

export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: string;
  suggestion?: string;
  details?: Record<string, unknown>;
}

export interface ScheduledOperation {
  order_id: string;
  operation_id: string;
  operation_type: string;
  sequence: number;
  machine_id: string;
  operator_id: string;
  quantity: number;
  part_family: string;
  start_bucket: number;
  end_bucket: number;
  start_time: string;
  end_time: string;
  day_index: number;
  shift: number;
  is_overtime: boolean;
  changeover_minutes_before: number;
  previous_family_on_machine: string | null;
  status: "planned" | "frozen" | "in_progress" | "completed";
  is_rework: boolean;
}

export interface OrderCompletion {
  order_id: string;
  customer: string;
  customer_tier: string;
  due_date: string;
  promised_completion: string;
  is_late: boolean;
  tardiness_hours: number;
  status: OrderStatus;
}

export interface MachineUtilization {
  machine_name: string;
  busy_hours: number;
  available_hours: number;
  utilization_pct: number;
}

export interface ScheduleMetrics {
  total_orders: number;
  not_late_orders: number;
  late_orders: number;
  at_risk_orders: number;
  on_track_orders: number;
  on_time_percentage: number;
  average_tardiness_hours: number;
  max_tardiness_hours: number;
  total_operations: number;
  overtime_operations: number;
  overtime_hours: number;
  machine_utilization: Record<string, MachineUtilization>;
  average_machine_utilization_pct: number;
  peak_machine_utilization_pct: number;
}

export interface CostBreakdown {
  operating_cost: number;
  overtime_cost: number;
  penalty_cost: number;
  changeover_cost: number;
  wasted_changeover_minutes: number;
  other_disruption_cost: number;
  total_cost: number;
  breakdown_pct?: Record<string, number>;
}

export interface ScheduleResult {
  strategy: Strategy;
  generated_at: string;
  solver_status: string;
  solver_wall_time_seconds: number;
  objective_value: number | null;
  operations: ScheduledOperation[];
  order_completions: OrderCompletion[];
  metrics: ScheduleMetrics;
  cost_breakdown: CostBreakdown;
  weights_used: Record<string, unknown>;
  comparison?: ReplanComparison;
  owner_action?: OwnerAction;
  frozen_operation_count?: number;
  reoptimized_operation_count?: number;
}

export interface ReplanComparison {
  now_bucket: number;
  moved_operations: Array<Record<string, unknown>>;
  moved_operation_count: number;
  order_changes: Array<{
    order_id: string;
    customer: string;
    customer_tier: string;
    old_completion: string;
    new_completion: string;
    old_status: OrderStatus;
    new_status: OrderStatus;
    moved: boolean;
    newly_late: boolean;
    delta_hours: number;
  }>;
  newly_late_orders: string[];
  new_overtime_operations: string[];
  cost_delta: Record<string, number>;
  disruption_cost: number;
  wasted_changeover_minutes_delta: number;
  generator_cost_note?: string;
}

export interface OwnerAction {
  has_action: boolean;
  headline: string;
  reasons?: string[];
  order_id?: string;
  customer?: string;
  customer_tier?: string;
  old_completion?: string;
  new_completion?: string;
  cost_delta?: Record<string, number>;
  detail?: string;
}

export interface Machine {
  machine_id: string;
  machine_name: string;
  machine_type: string;
  capabilities: string[];
  hourly_cost: number;
  overtime_cost: number;
  status: string;
  maintenance_windows: Array<Record<string, unknown>>;
  utilization: MachineUtilization;
  current_operation: ScheduledOperation | null;
  next_operation: ScheduledOperation | null;
  scheduled_operation_count: number;
  reliability: {
    breakdown_count: number;
    total_downtime_minutes: number;
    avg_downtime_minutes: number;
    mtbf_hours: number | null;
  };
}

export interface Operator {
  operator_id: string;
  name: string;
  skills: string[];
  qualified_machines: string[];
  hourly_rate: number;
  overtime_rate: number;
}

export interface OrderSummary {
  order_id: string;
  customer: string;
  customer_tier: string;
  part_family: string;
  quantity: number;
  due_date: string;
  release_date: string;
  material_available_date: string;
  revenue_priority: number;
  late_penalty_per_day: number;
  order_value: number;
  num_operations: number;
  promised_completion: string | null;
  status: OrderStatus;
  tardiness_hours: number;
  scheduled_operations: number;
}

export interface DashboardData {
  generated_at: string;
  strategy_in_use: Strategy;
  total_orders: number;
  on_time_percentage: number;
  late_orders: number;
  at_risk_orders: number;
  on_track_orders: number;
  average_machine_utilization_pct: number;
  peak_machine_utilization_pct: number;
  overtime_hours: number;
  total_cost: number;
  cost_breakdown: CostBreakdown;
  critical_alerts: Array<{ level: string; icon: string; message: string }>;
  active_disruption_count: number;
  recent_disruptions: DisruptionRecord[];
}

export interface DisruptionRecord {
  id: number;
  disruption_type: string;
  created_at: string;
  payload: Record<string, unknown>;
  applied: boolean;
  replan_result: ScheduleResult | null;
}

export interface StrategyComparisonRow {
  strategy: Strategy;
  strategy_label: string;
  solver_status: string;
  total_cost: number;
  operating_cost: number;
  overtime_cost: number;
  penalty_cost: number;
  changeover_cost: number;
  late_orders: number;
  on_time_percentage: number;
  average_tardiness_hours: number;
  max_tardiness_hours: number;
  average_machine_utilization_pct: number;
  peak_machine_utilization_pct: number;
  overtime_hours: number;
  robustness_score: number;
}

export interface StrategyRecommendation {
  recommended_strategy: Strategy | null;
  recommended_strategy_label?: string;
  reasons: string[];
  scores?: Record<string, number>;
  generated_at?: string;
}

export interface StrategyComparisonData {
  generated_at: string;
  comparison: StrategyComparisonRow[];
  recommendation: StrategyRecommendation;
}
