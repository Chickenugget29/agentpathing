import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AgentData } from '../data';
import { ChevronDown, ChevronRight, GitMerge } from 'lucide-react';

interface AgentPanelProps {
    agent: AgentData;
    delay?: number;
}

const AccordionItem: React.FC<{
    title: string;
    defaultOpen?: boolean;
    children: React.ReactNode;
    icon?: React.ReactNode;
}> = ({ title, defaultOpen = false, children, icon }) => {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    return (
        <div className="border border-white/5 rounded-lg bg-[#121214] overflow-hidden mb-3 shadow-sm">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between p-4 text-sm font-medium text-gray-300 hover:bg-white/5 transition-colors"
            >
                <div className="flex items-center gap-2">
                    {icon && <span className="opacity-50">{icon}</span>}
                    <span>{title}</span>
                </div>
                {isOpen ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronRight size={14} className="text-gray-500" />}
            </button>

            <AnimatePresence initial={false}>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25, ease: 'easeInOut' }}
                    >
                        <div className="p-4 pt-0 border-t border-transparent">
                            {children}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export const AgentPanel: React.FC<AgentPanelProps> = ({ agent, delay = 0 }) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay, ease: "easeOut" }}
            className="flex flex-col w-full"
        >
            {/* Agent Header */}
            <div className="mb-4 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                    <span className="font-mono text-xs font-bold text-white/60">{agent.id}</span>
                </div>
                <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                    {agent.name}
                </span>
            </div>

            <div className="flex flex-col gap-1">

                {/* Final Answer - Collapsed by default as per requirements */}
                <AccordionItem title="Final Answer" defaultOpen={false}>
                    <div className="bg-green-400/5 border border-green-400/10 rounded p-3 text-green-100 font-medium font-mono text-sm shadow-[0_0_15px_-3px_rgba(74,222,128,0.1)]">
                        {agent.finalAnswer}
                    </div>
                </AccordionItem>

                {/* Reasoning Steps - Expanded by default for better inspection flow? 
            User said "Expandable section: Reasoning".
            I'll interpret "Question -> Multiple reasonings -> Trust decision" as Reasoning being the core visible part. 
            I'll default Reasoning to OPEN.
        */}
                <AccordionItem title="Reasoning Process" defaultOpen={true}>
                    <div className="space-y-3 pl-1 relative">
                        {/* Vertical timeline line */}
                        <div className="absolute left-[11px] top-2 bottom-2 w-[1px] bg-white/5" />

                        {agent.reasoning.map((step, idx) => (
                            <div key={step.id} className="relative flex items-start gap-4 group">
                                <div className={`
                  relative z-10 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold border shrink-0 mt-0.5 transition-colors
                  ${step.isShared ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' : 'bg-gray-800 border-gray-700 text-gray-500'}
                `}>
                                    {idx + 1}
                                </div>
                                <div className="flex-1">
                                    <p className={`text-sm leading-relaxed ${step.isShared ? 'text-gray-200' : 'text-gray-400'}`}>
                                        {step.text}
                                    </p>
                                    {step.isShared && (
                                        <div className="mt-1 inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400/80 uppercase tracking-wide">
                                            <GitMerge size={10} /> Shared Reasoning
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </AccordionItem>

                {/* Assumptions */}
                <AccordionItem title="Assumptions" defaultOpen={false}>
                    <ul className="list-disc list-inside space-y-1 text-sm text-gray-400 marker:text-gray-600">
                        {agent.assumptions.map((asm, i) => (
                            <li key={i}>{asm}</li>
                        ))}
                    </ul>
                </AccordionItem>

            </div>
        </motion.div>
    );
};
