import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';

interface PromptInputProps {
    onAnalyze: (prompt: string) => void;
    onDemoAnalyze?: () => void;
    isAnalyzed: boolean;
    isLoading?: boolean;
}

export const PromptInput: React.FC<PromptInputProps> = ({
    onAnalyze,
    onDemoAnalyze,
    isAnalyzed,
    isLoading = false
}) => {
    const [value, setValue] = useState('');

    const handleAnalyze = () => {
        if (!value.trim()) return;
        onAnalyze(value.trim());
    };

    const handleDemo = () => {
        if (onDemoAnalyze) {
            onDemoAnalyze();
        }
    };

    return (
        <div className={`w-full max-w-2xl mx-auto transition-all duration-700 ease-out ${isAnalyzed ? 'mt-8 mb-12' : 'mt-32 mb-8'}`}>
            <div className="relative group">
                <textarea
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    placeholder="Describe a task or question for AI agents (e.g., 'How many piano tuners are there in Chicago?')..."
                    disabled={isLoading}
                    className="w-full h-32 bg-[#121214] border border-white/10 rounded-lg p-4 text-lg text-gray-200 placeholder:text-gray-600 focus:ring-1 focus:ring-white/20 focus:border-white/20 outline-none resize-none transition-all shadow-sm disabled:opacity-50"
                />
                <div className="absolute bottom-4 right-4 flex items-center gap-2">
                    {!isAnalyzed ? (
                        <>
                            {/* Demo button */}
                            <button
                                onClick={handleDemo}
                                disabled={isLoading}
                                className="px-4 py-2 text-gray-400 text-sm hover:text-white transition-colors disabled:opacity-50"
                            >
                                Try Demo
                            </button>

                            {/* Analyze button */}
                            <motion.button
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                                onClick={handleAnalyze}
                                disabled={!value.trim() || isLoading}
                                className="px-6 py-2 bg-white text-black font-semibold rounded-md text-sm hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 size={14} className="animate-spin" />
                                        Analyzing...
                                    </>
                                ) : (
                                    'Analyze Reasoning'
                                )}
                            </motion.button>
                        </>
                    ) : (
                        <span className="text-xs text-green-500 font-medium tracking-wide flex items-center gap-1">
                            ● Analysis Complete
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
};
