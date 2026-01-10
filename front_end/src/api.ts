import type {
    AgentData,
    AnalysisResult,
    GateDecisionInfo,
    ReasoningStep,
    TrustLevel,
    RobustnessOverview,
} from './types';

const API_BASE =
    (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE) ||
    '/api';

const AGENT_NAMES = ['Agent Alpha', 'Agent Beta', 'Agent Gamma', 'Agent Delta', 'Agent Epsilon'];
const AGENT_IDS = ['A', 'B', 'C', 'D', 'E'];

interface PipelineAgentResponse {
    agent_id: string;
    prompt_variant: string;
    plan: string;
    explanation: string;
    elapsed_ms: number;
}

interface PipelineAnalyzedReasoning {
    agent_id: string;
    fol_translation?: string;
    assumptions?: string[];
    steps?: string[];
    key_idea?: string;
    key_concepts?: string[];
}

interface PipelineRobustness {
    score?: string;
    confidence?: string;
    explanation?: string;
    recommendation?: string;
    total_agents?: number;
    distinct_families?: number;
}

interface PipelineGateDecision {
    decision: string;
    reason: string;
    action: string;
    suggestion?: string | null;
    color: string;
    icon: string;
}

interface PipelineResponse {
    task_id?: string;
    summary?: string;
    agent_responses?: PipelineAgentResponse[];
    analyzed_reasoning?: PipelineAnalyzedReasoning[];
    robustness?: PipelineRobustness;
    gate_decision?: PipelineGateDecision;
}

/**
 * Generate reasoning analysis using the backend MPRG pipeline.
 */
export async function generateAnalysis(userPrompt: string): Promise<AnalysisResult> {
    const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: userPrompt }),
    });

    if (!response.ok) {
        const error = await safeJson(response);
        throw new Error(error?.error || 'Failed to generate analysis');
    }

    const data: PipelineResponse = await response.json();
    return transformPipelineResponse(data);
}

async function safeJson(resp: Response): Promise<any | null> {
    try {
        return await resp.json();
    } catch {
        return null;
    }
}

function transformPipelineResponse(data: PipelineResponse): AnalysisResult {
    const analysisByAgent = new Map(
        (data.analyzed_reasoning || []).map((entry) => [entry.agent_id, entry]),
    );

    const agents: AgentData[] = (data.agent_responses || []).map((resp, index) => {
        const analysis = analysisByAgent.get(resp.agent_id);
        const reasoning = buildReasoningSteps(resp.plan, analysis);
        const assumptions = analysis?.assumptions ?? [];
        const finalAnswer = extractFinalAnswer(resp.explanation);

        return {
            id: AGENT_IDS[index] || resp.agent_id || `Agent-${index + 1}`,
            name: humanFriendlyName(resp.prompt_variant, index),
            finalAnswer,
            assumptions,
            reasoning,
            folTranslation: analysis?.fol_translation,
        };
    });

    detectSharedReasoning(agents);

    const gateDecision = data.gate_decision
        ? ({
              decision: data.gate_decision.decision,
              reason: data.gate_decision.reason,
              action: data.gate_decision.action,
              suggestion: data.gate_decision.suggestion,
              color: data.gate_decision.color,
              icon: data.gate_decision.icon,
          } satisfies GateDecisionInfo)
        : undefined;

    const robustness = data.robustness
        ? ({
              totalAgents: data.robustness.total_agents ?? agents.length,
              distinctFamilies: data.robustness.distinct_families ?? 0,
              confidence: data.robustness.confidence ?? 'Low',
              explanation: data.robustness.explanation,
              recommendation: data.robustness.recommendation,
          } satisfies RobustnessOverview)
        : undefined;

    const derivedTrust = determineTrustLevel(
        gateDecision?.decision,
        data.robustness?.score,
        agents,
    );

    const trustDescription =
        gateDecision?.reason ||
        data.robustness?.explanation ||
        data.summary ||
        derivedTrust.trustDescription;

    return {
        taskId: data.task_id,
        summary: data.summary,
        agents,
        gateDecision,
        robustness,
        trustLevel: derivedTrust.trustLevel,
        trustDescription,
    };
}

function humanFriendlyName(variant: string, index: number): string {
    if (!variant) return AGENT_NAMES[index] || `Agent ${index + 1}`;
    const label = variant.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    return `${label} Agent`;
}

function buildReasoningSteps(
    plan: string | undefined,
    analysis?: PipelineAnalyzedReasoning,
): ReasoningStep[] {
    const rawSteps = analysis?.steps?.length ? analysis.steps : parsePlan(plan);
    return rawSteps.map((text, idx) => ({
        id: idx + 1,
        text: text.trim(),
    }));
}

function parsePlan(plan: string | undefined): string[] {
    if (!plan) return [];
    return plan
        .split(/\n+/)
        .map((line) => line.trim())
        .map((line) => line.replace(/^(?:\d+[\).\s]+|[-*•]\s+)/, '').trim())
        .filter(Boolean)
        .slice(0, 10);
}

function extractFinalAnswer(explanation: string | undefined): string {
    if (!explanation) return 'No explanation provided.';
    const sentence = explanation.split(/[\n]+/).find((line) => line.trim().length > 8);
    return sentence ? sentence.trim() : explanation.slice(0, 180);
}

/**
 * Detect and flag shared reasoning statements.
 */
function detectSharedReasoning(agents: AgentData[]): void {
    if (agents.length < 2) return;

    const reasoningCounts: Record<string, number> = {};
    agents.forEach((agent) => {
        agent.reasoning.forEach((step) => {
            const normalized = step.text.toLowerCase().trim();
            reasoningCounts[normalized] = (reasoningCounts[normalized] || 0) + 1;
        });
    });

    agents.forEach((agent) => {
        agent.reasoning.forEach((step) => {
            const normalized = step.text.toLowerCase().trim();
            if (reasoningCounts[normalized] > 1) {
                step.isShared = true;
            }
        });
    });
}

function determineTrustLevel(
    gateDecision: string | undefined,
    robustnessScore: string | undefined,
    agents: AgentData[],
): { trustLevel: TrustLevel; trustDescription: string } {
    const score = gateDecision || robustnessScore;
    if (score) {
        return {
            trustLevel: mapScoreToTrust(score),
            trustDescription: '',
        };
    }
    return calculateTrustFromAgents(agents);
}

function mapScoreToTrust(score: string): TrustLevel {
    switch (score.toUpperCase()) {
        case 'FRAGILE':
        case 'BLOCK':
            return 'Fragile';
        case 'ROBUST':
        case 'ALLOW':
            return 'Robust';
        default:
            return 'Uncertain';
    }
}

function calculateTrustFromAgents(
    agents: AgentData[],
): { trustLevel: TrustLevel; trustDescription: string } {
    if (agents.length === 0) {
        return { trustLevel: 'Uncertain', trustDescription: 'No agent responses available.' };
    }

    const totalSteps = agents.reduce((sum, agent) => sum + agent.reasoning.length, 0);
    const sharedSteps = agents.reduce(
        (sum, agent) => sum + agent.reasoning.filter((step) => step.isShared).length,
        0,
    );
    const sharedRatio = totalSteps > 0 ? sharedSteps / totalSteps : 0;
    const sameAnswers = agents.every(
        (agent) => agent.finalAnswer.trim().toLowerCase() === agents[0].finalAnswer.trim().toLowerCase(),
    );

    if (sharedRatio > 0.7 && sameAnswers) {
        return {
            trustLevel: 'Fragile',
            trustDescription: 'High agreement using identical reasoning paths. Watch for collapse.',
        };
    }

    if (sharedRatio < 0.3 && !sameAnswers) {
        return {
            trustLevel: 'Robust',
            trustDescription: 'Diverse reasoning paths detected across agents.',
        };
    }

    return {
        trustLevel: 'Uncertain',
        trustDescription: 'Mixed agreement. Inspect reasoning differences manually.',
    };
}
