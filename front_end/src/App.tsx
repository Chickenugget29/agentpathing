import React, { useState } from 'react';
import { FRAGILE_SCENARIO, ROBUST_SCENARIO } from './data';
import { TopBar } from './components/TopBar';
import { PromptInput } from './components/PromptInput';
import { AgentPanel } from './components/AgentPanel';
import { TrustEvaluation } from './components/TrustEvaluation';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw } from 'lucide-react';

function App() {
    const [hasAnalyzed, setHasAnalyzed] = useState(false);
    const [scenarioId, setScenarioId] = useState<'fragile' | 'robust'>('fragile');
    const [key, setKey] = useState(0); // Used to force re-render animations on reset

    const currentScenario = scenarioId === 'fragile' ? FRAGILE_SCENARIO : ROBUST_SCENARIO;

    const handleAnalyze = () => {
        setHasAnalyzed(true);
    };

    const toggleScenario = () => {
        setScenarioId(prev => prev === 'fragile' ? 'robust' : 'fragile');
        // If we want to re-run the analysis visual flow when switching:
        // setHasAnalyzed(false); 
        // actually user might want to see the difference immediately?
        // User said: "All agents give the same answer using same reasoning -> Trust Level = Fragile"
        // "Switch Demo Scenario" -> implies switching the data.
        // I'll keep the analyzed state but re-trigger animations maybe?
        setKey(prev => prev + 1);
    };

    const reset = () => {
        setHasAnalyzed(false);
        setKey(prev => prev + 1);
    }

    return (
        <div className="min-h-screen bg-[#0A0A0B] flex flex-col font-sans selection:bg-white/20">
            <TopBar />

            <main className="flex-1 w-full max-w-7xl mx-auto px-6 pb-32">
                <PromptInput onAnalyze={handleAnalyze} isAnalyzed={hasAnalyzed} />

                <AnimatePresence mode="wait">
                    {hasAnalyzed && (
                        <div key={key} className="space-y-4"> {/* Key forces re-render for animation on scenario switch */}

                            {/* Agents Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-8 border-t border-white/5">
                                {currentScenario.agents.map((agent, index) => (
                                    <AgentPanel
                                        key={`${scenarioId}-${agent.id}`}
                                        agent={agent}
                                        delay={index * 0.15} // Staggered entrance
                                    />
                                ))}
                            </div>

                            {/* Trust Evaluation */}
                            <TrustEvaluation scenario={currentScenario} />

                        </div>
                    )}
                </AnimatePresence>

            </main>

            {/* Demo Controls - Fixed Bottom Bar or Floating */}
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 p-2 pl-4 pr-2 bg-[#18181b] border border-white/10 rounded-full shadow-2xl z-50">
                <span className="text-xs text-gray-500 font-medium whitespace-nowrap">
                    Demo Control ({scenarioId === 'fragile' ? 'Fragile' : 'Robust'})
                </span>
                <button
                    onClick={toggleScenario}
                    className="px-4 py-1.5 bg-white text-black text-xs font-bold rounded-full hover:bg-gray-200 transition-colors"
                >
                    Switch Scenario
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
