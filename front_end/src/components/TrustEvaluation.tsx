import React from 'react';
import { motion } from 'framer-motion';
import { Scenario } from '../data';
import { ShieldAlert, ShieldCheck, HelpCircle } from 'lucide-react';

interface TrustEvaluationProps {
    scenario: Scenario;
}

export const TrustEvaluation: React.FC<TrustEvaluationProps> = ({ scenario }) => {
    const isFragile = scenario.trustLevel === 'Fragile';
    const isRobust = scenario.trustLevel === 'Robust';

    const colorClass = isRobust ? 'text-green-400' : isFragile ? 'text-red-400' : 'text-yellow-400';
    const bgClass = isRobust ? 'bg-green-400/10' : isFragile ? 'bg-red-400/10' : 'bg-yellow-400/10';
    const borderClass = isRobust ? 'border-green-400/20' : isFragile ? 'border-red-400/20' : 'border-yellow-400/20';

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 1.5, ease: "easeOut" }} // Delays appearance to let reasoning be scanned first
            className="max-w-3xl mx-auto mt-16 p-8 rounded-2xl bg-[#0F0F10] border border-white/5 text-center relative overflow-hidden"
        >
            {/* Background Glow */}
            <div className={`absolute inset-0 opacity-5 blur-3xl pointer-events-none ${isRobust ? 'bg-green-500' : 'bg-red-500'}`} />

            <motion.div
                key={scenario.trustLevel}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.5 }}
            >
                <div className="inline-flex items-center gap-2 mb-4 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-mono text-gray-500 uppercase tracking-widest">
                    Consensus Analysis
                </div>

                <h2 className="text-4xl font-serif tracking-tight text-white mb-2 flex items-center justify-center gap-4">
                    <span className="opacity-50 font-sans text-2xl font-light text-gray-400">Trust Level:</span>
                    <span className={`${colorClass} font-semibold`}>{scenario.trustLevel}</span>
                </h2>

                <p className="text-gray-400 max-w-xl mx-auto mb-10 text-lg leading-relaxed">
                    {scenario.trustDescription}
                </p>

                {/* Minimal Bar Visualization */}
                <div className="relative h-2 w-64 mx-auto bg-gray-800 rounded-full overflow-hidden mb-4">
                    <div className="absolute inset-0 flex">
                        <div className="h-full w-1/3 border-r border-black/20 bg-red-500/20" /> {/* Fragile Zone */}
                        <div className="h-full w-1/3 border-r border-black/20 bg-yellow-500/20" /> {/* Uncertain Zone */}
                        <div className="h-full w-1/3 bg-green-500/20" /> {/* Robust Zone */}
                    </div>

                    {/* Indicator */}
                    <motion.div
                        className="absolute top-0 bottom-0 w-1 bg-white shadow-[0_0_10px_white] z-10"
                        animate={{
                            left: isRobust ? '85%' : isFragile ? '15%' : '50%'
                        }}
                        transition={{ type: "spring", stiffness: 60, damping: 15 }}
                    />
                </div>

                <div className="flex justify-between w-64 mx-auto text-[10px] text-gray-600 uppercase tracking-widest font-bold">
                    <span>Fragile</span>
                    <span>Robust</span>
                </div>

                <div className="mt-8 pt-6 border-t border-white/5 flex flex-col gap-2">
                    <p className="text-sm text-gray-500">
                        AI Reasoning Evaluation • Logic Consistency Check • Path Diversity Metric
                        <br />
                        <span className="text-white/20">ReasonStack Engine v0.9 (Beta)</span>
                    </p>
                </div>

            </motion.div>
        </motion.div>
    );
};
