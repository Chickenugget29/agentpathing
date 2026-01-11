export type AgentId = 'A' | 'B' | 'C' | 'D' | 'E' | string;

export type TrustLevel = 'Fragile' | 'Uncertain' | 'Robust';

export interface TaskFamily {
    familyId: string;
    repRunId: string;
    runIds: string[];
}

export interface TaskRun {
    id?: string;
    agentRole?: string;
    finalAnswer?: string;
    planSteps?: string[];
    assumptions?: string[];
    isValid?: boolean;
    error?: string | null;
}

export interface ReasoningStep {
    id: number;
    text: string;
    isShared?: boolean;
}

export interface AgentData {
    id: AgentId;
    name: string;
    finalAnswer: string;
    reasoning: ReasoningStep[];
    assumptions: string[];
    folTranslation?: string;
}

export interface GateDecisionInfo {
    decision: string;
    reason: string;
    action: string;
    suggestion?: string | null;
    color: string;
    icon: string;
}

export interface RobustnessOverview {
    totalAgents: number;
    distinctFamilies: number;
    confidence: string;
    explanation?: string;
    recommendation?: string;
}

export interface AnalysisResult {
    taskId?: string;
    summary?: string;
    trustLevel: TrustLevel;
    trustDescription: string;
    agents: AgentData[];
    gateDecision?: GateDecisionInfo;
    robustness?: RobustnessOverview;
    families?: TaskFamily[];
    runs?: TaskRun[];
    analysisError?: string | null;
    error?: string;
    agentCount?: number;
}

export interface Scenario extends AnalysisResult {
    id: 'fragile' | 'robust';
    label: string;
}

export interface ExecutionResult {
    success?: boolean;
    family_id?: string;
    family_size?: number;
    convergence_ratio?: number;
    execution_result?: {
        final_result?: string;
        confidence?: 'HIGH' | 'MEDIUM' | 'LOW';
        reasoning_summary?: string;
        caveats?: string[];
        executed_steps?: string[];
        executed?: boolean;
        error?: string;
    };
    error?: string;
}
