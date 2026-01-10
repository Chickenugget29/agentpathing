/**
 * API service for connecting frontend to backend
 */

const API_BASE = '/api';

export interface ReasoningStep {
    id: number;
    text: string;
    isShared?: boolean;
}

export interface AgentData {
    id: string;
    name: string;
    finalAnswer: string;
    reasoning: ReasoningStep[];
    assumptions: string[];
}

export interface AnalysisResult {
    task_id?: string;
    agents: AgentData[];
    trustLevel: 'Fragile' | 'Uncertain' | 'Robust';
    trustDescription: string;
    error?: string;
}

export interface GenerateResponse {
    runs?: Array<{
        agent_role: string;
        reasoning_summary?: {
            plan_steps: string[];
            assumptions: string[];
            final_answer: string;
        };
        is_valid: boolean;
    }>;
    error?: string;
}

/**
 * Generate reasoning analysis from user prompt
 */
export async function generateAnalysis(userPrompt: string): Promise<AnalysisResult> {
    try {
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ user_prompt: userPrompt }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to generate analysis');
        }

        const data: GenerateResponse = await response.json();

        // Transform backend response to frontend format
        return transformToScenario(data);
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * Create a task and get analysis
 */
export async function createTask(inputText: string): Promise<{ task_id: string }> {
    const response = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ input_text: inputText }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create task');
    }

    return response.json();
}

/**
 * Get task details
 */
export async function getTask(taskId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/tasks/${taskId}`);

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to get task');
    }

    return response.json();
}

/**
 * List recent tasks
 */
export async function listTasks(limit = 20): Promise<{ tasks: any[] }> {
    const response = await fetch(`${API_BASE}/tasks?limit=${limit}`);

    if (!response.ok) {
        return { tasks: [] };
    }

    return response.json();
}

/**
 * Transform backend response to frontend Scenario format
 */
function transformToScenario(data: GenerateResponse): AnalysisResult {
    const runs = data.runs || [];

    // Map agent roles to display names
    const agentNames = ['Agent Alpha', 'Agent Beta', 'Agent Gamma', 'Agent Delta', 'Agent Epsilon'];
    const agentIds = ['A', 'B', 'C', 'D', 'E'];

    const agents: AgentData[] = runs.map((run, index) => {
        const summary = run.reasoning_summary || {};
        const planSteps = summary.plan_steps || [];

        return {
            id: agentIds[index] || `${index}`,
            name: run.agent_role || agentNames[index] || `Agent ${index + 1}`,
            finalAnswer: summary.final_answer || 'No answer provided',
            reasoning: planSteps.map((step, stepIndex) => ({
                id: stepIndex + 1,
                text: step,
                isShared: false, // Will be calculated below
            })),
            assumptions: summary.assumptions || [],
        };
    });

    // Detect shared reasoning steps across agents
    detectSharedReasoning(agents);

    // Calculate trust level based on reasoning diversity
    const { trustLevel, trustDescription } = calculateTrustLevel(agents);

    return {
        agents,
        trustLevel,
        trustDescription,
    };
}

/**
 * Detect and mark shared reasoning steps across agents
 */
function detectSharedReasoning(agents: AgentData[]): void {
    if (agents.length < 2) return;

    // Create a map of reasoning text to count of agents using it
    const reasoningCounts: Record<string, number> = {};

    agents.forEach(agent => {
        agent.reasoning.forEach(step => {
            const normalized = step.text.toLowerCase().trim();
            reasoningCounts[normalized] = (reasoningCounts[normalized] || 0) + 1;
        });
    });

    // Mark steps as shared if they appear in more than one agent
    agents.forEach(agent => {
        agent.reasoning.forEach(step => {
            const normalized = step.text.toLowerCase().trim();
            if (reasoningCounts[normalized] > 1) {
                step.isShared = true;
            }
        });
    });
}

/**
 * Calculate trust level based on agent diversity
 */
function calculateTrustLevel(agents: AgentData[]): { trustLevel: 'Fragile' | 'Uncertain' | 'Robust'; trustDescription: string } {
    if (agents.length === 0) {
        return { trustLevel: 'Uncertain', trustDescription: 'No agent responses available.' };
    }

    // Count shared reasoning steps
    const totalSteps = agents.reduce((sum, agent) => sum + agent.reasoning.length, 0);
    const sharedSteps = agents.reduce((sum, agent) =>
        sum + agent.reasoning.filter(step => step.isShared).length, 0
    );

    const sharedRatio = totalSteps > 0 ? sharedSteps / totalSteps : 0;

    // Check if all answers are the same
    const answers = agents.map(a => a.finalAnswer.toLowerCase().trim());
    const uniqueAnswers = new Set(answers).size;
    const answerAgreement = uniqueAnswers === 1;

    if (sharedRatio > 0.6 && answerAgreement) {
        return {
            trustLevel: 'Fragile',
            trustDescription: 'High agreement, but identical reasoning paths suggest model collapse or shared error modes.',
        };
    }

    if (answerAgreement && sharedRatio < 0.3) {
        return {
            trustLevel: 'Robust',
            trustDescription: 'Strong consensus reached via independent reasoning paths.',
        };
    }

    return {
        trustLevel: 'Uncertain',
        trustDescription: 'Mixed signals - some agreement with varied reasoning approaches.',
    };
}
