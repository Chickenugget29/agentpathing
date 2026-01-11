import type {
    AgentData,
    AnalysisResult,
    GateDecisionInfo,
    ReasoningStep,
    TrustLevel,
    RobustnessOverview,
    TaskFamily,
    TaskRun,
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

interface TaskResponsePayload {
    task: {
        _id: string;
        robustness_status?: string;
        num_families?: number;
        analysis_error?: string | null;
        families?: Array<{ family_id: string; rep_run_id: string; run_ids: string[] }>;
    };
    runs: Array<{
        _id?: string;
        agent_role?: string;
        plan_steps?: string[];
        assumptions?: string[];
        final_answer?: string;
        is_valid?: boolean;
        raw_json?: Record<string, any>;
    }>;
}

/**
 * Generate reasoning analysis by preferring the task-based backend,
 * falling back to the legacy pipeline if necessary.
 */
export async function generateAnalysis(userPrompt: string): Promise<AnalysisResult> {
    try {
        return await generateFromTaskApi(userPrompt);
    } catch (taskError) {
        console.warn('Task-based API failed, falling back to pipeline', taskError);
    }

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

async function generateFromTaskApi(userPrompt: string): Promise<AnalysisResult> {
    const createRes = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input_text: userPrompt }),
    });

    if (!createRes.ok) {
        const error = await safeJson(createRes);
        throw new Error(error?.error || 'Failed to create task');
    }

    const { task_id } = await createRes.json();
    const taskRes = await fetch(`${API_BASE}/tasks/${task_id}`);
    if (!taskRes.ok) {
        const error = await safeJson(taskRes);
        throw new Error(error?.error || 'Failed to fetch task');
    }
    const payload: TaskResponsePayload = await taskRes.json();
    return transformTaskPayload(task_id, payload);
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

function transformTaskPayload(taskId: string, payload: TaskResponsePayload): AnalysisResult {
    const { task, runs } = payload;
    const summarizedRuns = runs.map<TaskRun>((run) => {
        const summary = (run.raw_json?.reasoning_summary as Record<string, any>) || {};
        return {
            id: run._id,
            agentRole: run.agent_role,
            finalAnswer: run.final_answer || summary.final_answer,
            planSteps: run.plan_steps?.length ? run.plan_steps : summary.plan_steps || [],
            assumptions: run.assumptions?.length ? run.assumptions : summary.assumptions || [],
            isValid: run.is_valid,
        };
    });
    const agents: AgentData[] = runs.slice(0, AGENT_IDS.length).map((run, index) => {
        const summary = (run.raw_json?.reasoning_summary as Record<string, any>) || {};
        const planSteps = run.plan_steps && run.plan_steps.length > 0 ? run.plan_steps : summary.plan_steps || [];
        const assumptions = run.assumptions && run.assumptions.length > 0 ? run.assumptions : summary.assumptions || [];
        const planText = planSteps.map((step, idx) => `${idx + 1}. ${step}`).join('\n');
        const reasoning = buildReasoningSteps(planText, undefined);
        const finalAnswer = run.final_answer || summary.final_answer || 'No answer provided';
        return {
            id: AGENT_IDS[index] || run._id || `Agent-${index + 1}`,
            name: humanFriendlyName(run.agent_role || '', index),
            finalAnswer,
            assumptions,
            reasoning,
        } satisfies AgentData;
    });

    detectSharedReasoning(agents);

    const robustnessStatus = (task.robustness_status || '').toUpperCase();
    const trust = mapRobustnessToTrust(robustnessStatus, agents);
    const robustness: RobustnessOverview = {
        totalAgents: runs.length,
        distinctFamilies: task.num_families ?? task.families?.length ?? 0,
        confidence: robustnessStatus === 'ROBUST' ? 'High' : 'Low',
        explanation: `Robustness status: ${robustnessStatus || 'UNKNOWN'}`,
    };
    const families: TaskFamily[] = (task.families || []).map((family) => ({
        familyId: family.family_id,
        repRunId: family.rep_run_id,
        runIds: family.run_ids || [],
    }));

    return {
        taskId,
        summary: `Robustness: ${robustnessStatus || 'UNKNOWN'}`,
        trustLevel: trust.trustLevel,
        trustDescription: trust.trustDescription,
        agents,
        robustness,
        families,
        runs: summarizedRuns,
        analysisError: task.analysis_error ?? null,
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
