export type AgentId = 'A' | 'B' | 'C' | 'D' | 'E' | string;

export type TrustLevel = 'Fragile' | 'Uncertain' | 'Robust';

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
    error?: string;
}

export interface Scenario extends AnalysisResult {
    id: 'fragile' | 'robust';
    label: string;
}
