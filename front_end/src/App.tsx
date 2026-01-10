import React, { useState } from 'react';
import { FRAGILE_SCENARIO, ROBUST_SCENARIO } from './data';
import { generateAnalysis } from './api';
import type { Scenario, AnalysisResult } from './types';
import { TopBar } from './components/TopBar';
import { PromptInput } from './components/PromptInput';
import { AgentPanel } from './components/AgentPanel';
import { TrustEvaluation } from './components/TrustEvaluation';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, Loader2 } from 'lucide-react';

function App() {
    const [hasAnalyzed, setHasAnalyzed] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [scenarioId, setScenarioId] = useState<'fragile' | 'robust' | 'live'>('fragile');
    const [liveResult, setLiveResult] = useState<AnalysisResult | null>(null);
    const [key, setKey] = useState(0);

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
    }

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
