import React from 'react';

export const TopBar: React.FC = () => {
    return (
        <div className="w-full flex items-center justify-between p-6 border-b border-white/5">
            <div className="flex items-center gap-2">
                {/* Simple geometric logo placeholder */}
                <div className="w-4 h-4 bg-white rounded-full opacity-90" />
                <span className="text-lg font-medium tracking-tight text-white">ReasonStack</span>
            </div>

            <div className="px-3 py-1 rounded-full bg-white/5 border border-white/10">
                <span className="text-xs uppercase tracking-wider font-semibold text-gray-400">
                    Reasoning Inspection Mode
                </span>
            </div>
        </div>
    );
};
