import React, { useMemo, useState } from 'react';
import { FRAGILE_SCENARIO, ROBUST_SCENARIO } from './data';
import { generateAnalysis, executeConvergentPlan } from './api';
import type { Scenario, AnalysisResult, TaskFamily, TaskRun, ExecutionResult } from './types';
import { TopBar } from './components/TopBar';
import { PromptInput } from './components/PromptInput';
import { AgentPanel } from './components/AgentPanel';
import { TrustEvaluation } from './components/TrustEvaluation';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, Loader2, Zap, CheckCircle2, AlertTriangle } from 'lucide-react';

function App() {
    const [hasAnalyzed, setHasAnalyzed] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [scenarioId, setScenarioId] = useState<'fragile' | 'robust' | 'live'>('fragile');
    const [liveResult, setLiveResult] = useState<AnalysisResult | null>(null);
    const [key, setKey] = useState(0);
    const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
    const [isExecuting, setIsExecuting] = useState(false);
    const [executionError, setExecutionError] = useState<string | null>(null);

    // Get current scenario data
    const currentScenario: Scenario = scenarioId === 'live' && liveResult
        ? {
            id: 'robust', // Use robust styling for live results
            label: 'Live Analysis',
            ...liveResult,
        }
        : scenarioId === 'fragile' ? FRAGILE_SCENARIO : ROBUST_SCENARIO;

    const handleAnalyze = async (prompt: string) => {
        setError(null);
        setIsLoading(true);

        try {
            const result = await generateAnalysis(prompt);
            setLiveResult(result);
            setScenarioId('live');
            setHasAnalyzed(true);
            setKey(prev => prev + 1);
        } catch (err) {
            console.error('Analysis failed:', err);
            setError(err instanceof Error ? err.message : 'Analysis failed');
            // Fall back to demo mode
            setScenarioId('fragile');
            setHasAnalyzed(true);
        } finally {
            setIsLoading(false);
        }
    };

    const handleDemoAnalyze = () => {
        // For demo mode - use static data
        setError(null);
        setLiveResult(null);
        setHasAnalyzed(true);
    };

    const toggleScenario = () => {
        if (scenarioId === 'live') {
            setScenarioId('fragile');
        } else {
            setScenarioId(prev => prev === 'fragile' ? 'robust' : 'fragile');
        }
        setKey(prev => prev + 1);
    };

    const reset = () => {
        setHasAnalyzed(false);
        setLiveResult(null);
        setError(null);
        setScenarioId('fragile');
        setKey(prev => prev + 1);
        setExecutionResult(null);
        setExecutionError(null);
    }

    const handleExecute = async () => {
        if (!liveResult?.taskId) return;

        setIsExecuting(true);
        setExecutionError(null);

        try {
            const result = await executeConvergentPlan(liveResult.taskId);
            setExecutionResult(result);
        } catch (err) {
            console.error('Execution failed:', err);
            setExecutionError(err instanceof Error ? err.message : 'Execution failed');
        } finally {
            setIsExecuting(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0A0A0B] flex flex-col font-sans selection:bg-white/20">
            <TopBar />

            <main className="flex-1 w-full max-w-7xl mx-auto px-6 pb-32">
                <PromptInput
                    onAnalyze={handleAnalyze}
                    onDemoAnalyze={handleDemoAnalyze}
                    isAnalyzed={hasAnalyzed}
                    isLoading={isLoading}
                />

                {/* Error Message */}
                {error && (
                    <div className="max-w-2xl mx-auto mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-red-300 text-sm">
                        <span className="font-medium">Error:</span> {error}
                        <span className="text-gray-400 ml-2">(Showing demo data)</span>
                    </div>
                )}

                {/* Loading State */}
                {isLoading && (
                    <div className="flex flex-col items-center justify-center py-16">
                        <Loader2 className="w-8 h-8 text-white animate-spin mb-4" />
                        <p className="text-gray-400">Generating analysis with multiple agents...</p>
                    </div>
                )}

                <AnimatePresence mode="wait">
                    {hasAnalyzed && !isLoading && (
                        <div key={key} className="space-y-4">

                            {/* Live vs Demo indicator */}
                            {scenarioId === 'live' && (
                                <div className="flex items-center justify-center gap-2 py-2">
                                    <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-green-900/50 border border-green-500/50 rounded-full text-xs text-green-400">
                                        <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></span>
                                        Live API Response
                                    </span>
                                </div>
                            )}

                            {/* Agents Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-8 border-t border-white/5">
                                {currentScenario.agents.slice(0, 3).map((agent, index) => (
                                    <AgentPanel
                                        key={`${scenarioId}-${agent.id}`}
                                        agent={agent}
                                        delay={index * 0.15}
                                    />
                                ))}
                            </div>

                            {/* Trust Evaluation */}
                            <TrustEvaluation scenario={currentScenario} />

                        </div>
                    )}
                </AnimatePresence>

                {scenarioId === 'live' && liveResult?.runs && liveResult.runs.length > 0 && (
                    <LiveFamiliesSection result={liveResult} />
                )}

                {/* Final Executor Section */}
                {scenarioId === 'live' && liveResult?.taskId && liveResult?.families && liveResult.families.length > 0 && (
                    <section className="mt-12 space-y-6">
                        <div className="flex items-center justify-between flex-wrap gap-4">
                            <div>
                                <p className="text-sm uppercase tracking-[0.3em] text-gray-500">Final Step</p>
                                <h2 className="text-2xl font-semibold text-white">Execute Convergent Plan</h2>
                            </div>
                            {!executionResult && !isExecuting && (
                                <button
                                    onClick={handleExecute}
                                    className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-semibold rounded-xl hover:from-emerald-400 hover:to-teal-400 transition-all shadow-lg shadow-emerald-500/25"
                                >
                                    <Zap className="w-5 h-5" />
                                    Run Final Agent
                                </button>
                            )}
                        </div>

                        {isExecuting && (
                            <div className="flex flex-col items-center justify-center py-12 bg-white/5 border border-white/10 rounded-2xl">
                                <Loader2 className="w-8 h-8 text-emerald-400 animate-spin mb-4" />
                                <p className="text-gray-400">Executing convergent plan with final agent...</p>
                            </div>
                        )}

                        {executionError && (
                            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                                <div className="text-sm text-red-200">
                                    <span className="font-semibold">Execution failed:</span> {executionError}
                                </div>
                            </div>
                        )}

                        {executionResult && (
                            <ExecutionResultCard result={executionResult} />
                        )}
                    </section>
                )}
            </main>

            {/* Demo Controls - Fixed Bottom Bar */}
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 p-2 pl-4 pr-2 bg-[#18181b] border border-white/10 rounded-full shadow-2xl z-50">
                <span className="text-xs text-gray-500 font-medium whitespace-nowrap">
                    Mode: {scenarioId === 'live' ? 'Live' : scenarioId === 'fragile' ? 'Demo (Fragile)' : 'Demo (Robust)'}
                </span>
                <button
                    onClick={toggleScenario}
                    className="px-4 py-1.5 bg-white text-black text-xs font-bold rounded-full hover:bg-gray-200 transition-colors"
                >
                    Switch Demo
                </button>
                <button
                    onClick={reset}
                    className="p-1.5 text-gray-500 hover:text-white transition-colors rounded-full"
                    title="Reset Interface"
                >
                    <RefreshCw size={14} />
                </button>
            </div>

        </div>
    );
}

export default App;

const LiveFamiliesSection: React.FC<{ result: AnalysisResult }> = ({ result }) => {
    const runs: TaskRun[] = result.runs || [];
    const families: TaskFamily[] = result.families || [];
    const metrics = useMemo(() => {
        const validRuns = runs.filter((run) => run.isValid).length;
        const totalRuns = runs.length;
        const familyCount = families.length;
        const robustnessStatus = (result.summary || '').toUpperCase().replace('ROBUSTNESS:', '').trim() || result.trustLevel.toUpperCase();
        const agreement = computeAnswerAgreement(runs);
        return { validRuns, totalRuns, familyCount, robustnessStatus, agreement };
    }, [runs, families, result.summary, result.trustLevel]);

    const { groups, unassigned } = useMemo(() => buildFamilyGroups(families, runs), [families, runs]);

    return (
        <section className="mt-16 space-y-6">
            <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                    <p className="text-sm uppercase tracking-[0.3em] text-gray-500">Live Inspection</p>
                    <h2 className="text-2xl font-semibold text-white">Reasoning Families</h2>
                </div>
                <div className="text-sm text-gray-400">Task ID: {result.taskId}</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <SummaryTile label="Agents (valid / total)" value={`${metrics.validRuns} / ${metrics.totalRuns}`} />
                <SummaryTile label="Reasoning Families" value={metrics.familyCount || '-'} />
                <SummaryTile
                    label="Robustness Status"
                    value={<span className={`px-3 py-1 rounded-full text-xs font-semibold ${badgeClass(metrics.robustnessStatus)}`}>{metrics.robustnessStatus || 'UNKNOWN'}</span>}
                />
                <SummaryTile label="Answer Agreement" value={metrics.agreement} />
            </div>

            {result.analysisError && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-200">
                    Analysis error: {result.analysisError}
                </div>
            )}

            <div className="space-y-6">
                {groups.length ? (
                    groups.map((group, idx) => (
                        <div key={idx} className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-lg font-semibold text-white">{group.title}</h3>
                                <span className="text-sm text-gray-400">{group.members.length} runs</span>
                            </div>
                            {group.members.length ? (
                                <>
                                    {group.members
                                        .filter((run) => run.id && run.id === group.repRunId)
                                        .map((run, runIndex) => (
                                            <RunCard key={run.id || runIndex} run={run} index={1} highlight label="Representative" />
                                        ))}
                                    {group.members
                                        .filter((run) => !group.repRunId || run.id !== group.repRunId)
                                        .map((run, runIndex) => (
                                            <RunCard key={run.id || runIndex} run={run} index={runIndex + 2} />
                                        ))}
                                </>
                            ) : (
                                <p className="text-sm text-gray-500">No runs assigned.</p>
                            )}
                        </div>
                    ))
                ) : (
                    <div className="border border-dashed border-white/10 rounded-xl p-6 text-sm text-gray-400">
                        No reasoning families detected yet.
                    </div>
                )}

                {unassigned.length > 0 && (
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-3">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-white">Unassigned Runs</h3>
                            <span className="text-sm text-gray-400">{unassigned.length} runs</span>
                        </div>
                        <div className="space-y-3">
                            {unassigned.map((run, idx) => (
                                <RunCard key={run.id || idx} run={run} index={idx + 1} />
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </section>
    );
};

const SummaryTile: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
        <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
        <div className="mt-2 text-xl font-semibold text-white">{value}</div>
    </div>
);

const RunCard: React.FC<{ run: TaskRun; index: number; highlight?: boolean; label?: string }> = ({ run, index, highlight = false, label }) => {
    const steps = run.planSteps || [];
    const assumptions = run.assumptions || [];
    return (
        <div className={`rounded-xl border ${highlight ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-white/10 bg-black/10'} p-4 space-y-3`}>
            <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-white">
                    Run {index} — {run.agentRole || 'Agent'} {label ? `(${label})` : ''}
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${run.isValid ? 'bg-emerald-500/20 text-emerald-200' : 'bg-red-500/20 text-red-200'}`}>
                    {run.isValid ? 'VALID' : 'INVALID'}
                </span>
            </div>
            <div className="text-sm text-gray-300">
                <span className="font-semibold text-white">Final answer:</span> {run.finalAnswer || 'No answer provided'}
            </div>
            <div>
                <div className="text-xs uppercase tracking-wide text-gray-500">Plan Steps</div>
                <div className="flex flex-wrap gap-2 mt-1">
                    {steps.length
                        ? steps.map((step, idx) => (
                            <span key={idx} className="bg-black/30 border border-white/10 rounded-full text-xs px-2 py-1">
                                {step}
                            </span>
                        ))
                        : <span className="text-xs text-gray-500">None</span>}
                </div>
            </div>
            <div>
                <div className="text-xs uppercase tracking-wide text-gray-500">Assumptions</div>
                <div className="flex flex-wrap gap-2 mt-1">
                    {assumptions.length
                        ? assumptions.map((asm, idx) => (
                            <span key={idx} className="bg-black/30 border border-white/10 rounded-full text-xs px-2 py-1">
                                {asm}
                            </span>
                        ))
                        : <span className="text-xs text-gray-500">None</span>}
                </div>
            </div>
        </div>
    );
};

function computeAnswerAgreement(runs: TaskRun[]): string {
    const valid = runs.filter((run) => run.isValid && (run.finalAnswer || '').trim());
    if (!valid.length) return 'N/A';
    const counts = valid.reduce<Record<string, number>>((acc, run) => {
        const key = (run.finalAnswer || '').trim().toLowerCase();
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    const max = Math.max(...Object.values(counts));
    return `${Math.round((max / valid.length) * 100)}%`;
}

function buildFamilyGroups(families: TaskFamily[], runs: TaskRun[]) {
    const runMap = new Map<string, TaskRun>();
    runs.forEach((run) => {
        if (run.id) runMap.set(run.id, run);
    });
    const assigned = new Set<string>();
    const groups = families.map((family, index) => {
        const members = family.runIds
            .map((runId) => runMap.get(runId))
            .filter((run): run is TaskRun => Boolean(run));
        members.forEach((run) => run.id && assigned.add(run.id));
        return {
            title: `Family ${index + 1}`,
            members,
            repRunId: family.repRunId,
        };
    });
    const unassigned = runs.filter((run) => run.id && !assigned.has(run.id));
    return { groups, unassigned };
}

function badgeClass(status: string) {
    const key = status.toUpperCase();
    if (key.includes('ROBUST')) return 'bg-emerald-500/20 text-emerald-200';
    if (key.includes('FRAGILE')) return 'bg-red-500/20 text-red-200';
    if (key.includes('INSUFFICIENT')) return 'bg-gray-600/30 text-gray-200';
    return 'bg-gray-700/40 text-gray-200';
}

const ExecutionResultCard: React.FC<{ result: ExecutionResult }> = ({ result }) => {
    const exec = result.execution_result;

    if (!exec) {
        return (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-200">
                No execution result available
            </div>
        );
    }

    if (exec.error) {
        return (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-200">
                <span className="font-semibold">Execution Error:</span> {exec.error}
            </div>
        );
    }

    const confidenceColors = {
        HIGH: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
        MEDIUM: 'bg-amber-500/20 text-amber-200 border-amber-500/30',
        LOW: 'bg-red-500/20 text-red-200 border-red-500/30',
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 border border-emerald-500/30 rounded-2xl p-6 space-y-6"
        >
            {/* Header with success indicator */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-500/20 rounded-full">
                        <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-white">Execution Complete</h3>
                        <p className="text-sm text-gray-400">
                            Convergence: {result.family_size}/{Math.round((result.convergence_ratio || 0) * result.family_size! / (result.convergence_ratio || 1))} agents agreed
                        </p>
                    </div>
                </div>
                {exec.confidence && (
                    <span className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${confidenceColors[exec.confidence] || confidenceColors.MEDIUM}`}>
                        {exec.confidence} CONFIDENCE
                    </span>
                )}
            </div>

            {/* Final Result */}
            <div className="bg-black/30 rounded-xl p-5">
                <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">Final Result</div>
                <div className="text-lg text-white font-medium leading-relaxed">
                    {exec.final_result || 'No result provided'}
                </div>
            </div>

            {/* Reasoning Summary */}
            {exec.reasoning_summary && (
                <div>
                    <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">Reasoning Summary</div>
                    <p className="text-gray-300 text-sm">{exec.reasoning_summary}</p>
                </div>
            )}

            {/* Executed Steps */}
            {exec.executed_steps && exec.executed_steps.length > 0 && (
                <div>
                    <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">Executed Steps</div>
                    <div className="space-y-2">
                        {exec.executed_steps.map((step, idx) => (
                            <div key={idx} className="flex items-start gap-3 text-sm">
                                <span className="flex-shrink-0 w-6 h-6 bg-emerald-500/20 text-emerald-300 rounded-full flex items-center justify-center text-xs font-semibold">
                                    {idx + 1}
                                </span>
                                <span className="text-gray-300">{step}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Caveats */}
            {exec.caveats && exec.caveats.length > 0 && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
                    <div className="text-xs uppercase tracking-wide text-amber-400 mb-2 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        Caveats & Limitations
                    </div>
                    <ul className="list-disc list-inside text-sm text-amber-200/80 space-y-1">
                        {exec.caveats.map((caveat, idx) => (
                            <li key={idx}>{caveat}</li>
                        ))}
                    </ul>
                </div>
            )}
        </motion.div>
    );
};

