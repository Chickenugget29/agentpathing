export interface FamilyRecord {
  family_id: string;
  rep_run_id: string;
  run_ids: string[];
}

export interface TaskRecord {
  _id: string;
  input_text?: string;
  status?: string;
  robustness_status?: string;
  num_families?: number;
  analysis_error?: string | null;
  families?: FamilyRecord[];
}

export interface RunRecord {
  _id?: string;
  agent_role?: string;
  final_answer?: string;
  plan_steps?: string[];
  assumptions?: string[];
  is_valid?: boolean;
  raw_json?: Record<string, unknown>;
  created_at?: string;
}

export interface TaskPayload {
  task: TaskRecord;
  runs: RunRecord[];
}
