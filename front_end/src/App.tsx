import React, { useMemo, useState } from 'react';
import { createTask, fetchTask } from './api';
import type { FamilyRecord, RunRecord, TaskRecord } from './types';

interface LoadedTask {
  task: TaskRecord;
  runs: RunRecord[];
  taskId: string;
}

const statusStyles: Record<string, string> = {
  ROBUST: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
  FRAGILE: 'bg-rose-500/20 text-rose-300 border border-rose-500/30',
  INSUFFICIENT_DATA: 'bg-slate-500/20 text-slate-300 border border-slate-500/30',
  ERROR: 'bg-rose-500/20 text-rose-300 border border-rose-500/30',
};

function statusBadgeClass(status?: string) {
  const key = (status || '').toUpperCase();
  return statusStyles[key] || 'bg-slate-700/60 text-slate-300 border border-slate-600/60';
}

function computeAnswerAgreement(runs: RunRecord[]): string {
  const valid = runs.filter((run) => run.is_valid && (run.final_answer || '').trim());
  if (!valid.length) return 'N/A';
  const counts = valid.reduce<Map<string, number>>((acc, run) => {
    const answer = (run.final_answer || '').trim().toLowerCase();
    acc.set(answer, (acc.get(answer) || 0) + 1);
    return acc;
  }, new Map());
  const maxCount = Math.max(...counts.values());
  const percent = Math.round((maxCount / valid.length) * 100);
  return `${percent}% align`;
}

function buildFamilyViews(task: TaskRecord, runs: RunRecord[]) {
  const runMap = new Map<string, RunRecord>();
  const assigned = new Set<string>();
  runs.forEach((run) => {
    if (run._id) {
      runMap.set(run._id, run);
    }
  });

  const families = (task.families || []).map((family, index) => {
    const members = family.run_ids
      .map((id) => runMap.get(id))
      .filter((run): run is RunRecord => Boolean(run));
    members.forEach((run) => run._id && assigned.add(run._id));
    return { title: `Family ${index + 1}`, repRunId: family.rep_run_id, members };
  });

  const unassigned = runs.filter((run) => run._id && !assigned.has(run._id));
  return { families, unassigned };
}

const RunCard: React.FC<{
  run: RunRecord;
  index: number;
  highlight?: boolean;
  label?: string;
}> = ({ run, index, highlight = false, label }) => {
  const steps = run.plan_steps || [];
  const assumptions = run.assumptions || [];
  const badgeClass = run.is_valid ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300';
  const badgeLabel = run.is_valid ? 'VALID' : 'INVALID';

  return (
    <div className={`rounded-xl border border-white/10 p-4 ${highlight ? 'bg-white/5' : 'bg-transparent'}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-sm text-slate-200">
          Run {index} — {run.agent_role || 'Agent'} {label ? `(${label})` : ''}
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${badgeClass}`}>{badgeLabel}</span>
      </div>
      <p className="text-sm text-slate-400 mt-2">
        <span className="font-semibold text-slate-200">Final answer:</span> {run.final_answer || '-'}
      </p>
      <div className="mt-3">
        <p className="text-xs uppercase tracking-wide text-slate-500">Plan Steps</p>
        <div className="mt-1 flex flex-wrap gap-2">
          {steps.length ? (
            steps.map((step, idx) => (
              <span key={idx} className="text-xs bg-slate-800/80 border border-slate-700 px-2 py-1 rounded-full">
                {step}
              </span>
            ))
          ) : (
            <span className="text-xs text-slate-500">None</span>
          )}
        </div>
      </div>
      <div className="mt-3">
        <p className="text-xs uppercase tracking-wide text-slate-500">Assumptions</p>
        <div className="mt-1 flex flex-wrap gap-2">
          {assumptions.length ? (
            assumptions.map((assumption, idx) => (
              <span key={idx} className="text-xs bg-slate-800/80 border border-slate-700 px-2 py-1 rounded-full">
                {assumption}
              </span>
            ))
          ) : (
            <span className="text-xs text-slate-500">None</span>
          )}
        </div>
      </div>
    </div>
  );
};

const SummaryCard: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="bg-slate-900/80 border border-white/5 rounded-xl p-4">
    <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
    <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
  </div>
);

const App: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<LoadedTask | null>(null);

  const metrics = useMemo(() => {
    if (!loaded) {
      return {
        validRuns: 0,
        totalRuns: 0,
        families: 0,
        robustness: 'PENDING',
        agreement: 'N/A',
      };
    }
    const validRuns = loaded.runs.filter((run) => run.is_valid).length;
    const totalRuns = loaded.runs.length;
    const families = loaded.task.num_families ?? loaded.task.families?.length ?? 0;
    const robustness = loaded.task.robustness_status || 'PENDING';
    const agreement = computeAnswerAgreement(loaded.runs);
    return { validRuns, totalRuns, families, robustness, agreement };
  }, [loaded]);

  const handleRun = async () => {
    if (!prompt.trim()) {
      setError('Please enter a task prompt.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { task_id } = await createTask(prompt.trim());
      const payload = await fetchTask(task_id);
      setLoaded({ task: payload.task, runs: payload.runs, taskId: task_id });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run task.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (!loaded) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchTask(loaded.taskId);
      setLoaded({ task: payload.task, runs: payload.runs, taskId: loaded.taskId });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh task.');
    } finally {
      setLoading(false);
    }
  };

  const { families, unassigned } = useMemo(() => {
    if (!loaded) return { families: [], unassigned: [] as RunRecord[] };
    return buildFamilyViews(loaded.task, loaded.runs);
  }, [loaded]);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        <header>
          <p className="text-sm uppercase tracking-[0.4em] text-slate-500">Reasoning Guard</p>
          <h1 className="text-4xl font-semibold mt-2">Multi-Path Reasoning Inspection</h1>
          <p className="text-slate-400 mt-1">
            Fan out multiple agents, cluster their thinking, and inspect robustness before execution.
          </p>
        </header>

        <section className="bg-slate-900/80 border border-white/5 rounded-2xl p-6 space-y-4">
          <label className="text-sm font-medium text-slate-200">Task prompt</label>
          <textarea
            className="w-full min-h-[140px] rounded-xl bg-slate-950/60 border border-white/10 p-4 text-base text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            placeholder="Describe the workflow or question..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={loading}
          />
          {error && <div className="text-sm text-rose-300">{error}</div>}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleRun}
              disabled={loading}
              className="px-6 py-3 rounded-xl bg-emerald-500 text-slate-900 font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? 'Running...' : 'Generate & Check'}
            </button>
            {loaded && (
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="px-5 py-3 rounded-xl border border-white/10 text-slate-200 hover:border-white/30 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Refresh Results
              </button>
            )}
          </div>
        </section>

        {loaded && (
          <section className="space-y-6">
            <div>
              <div className="text-sm text-slate-500 mb-2">Task ID</div>
              <code className="bg-slate-900/80 border border-white/5 rounded-xl px-4 py-2 text-sm text-slate-300">
                {loaded.taskId}
              </code>
            </div>

            <div className="grid md:grid-cols-4 gap-4">
              <SummaryCard label="Agents (valid / total)" value={`${metrics.validRuns} / ${metrics.totalRuns}`} />
              <SummaryCard label="Reasoning Families" value={metrics.families || '-'} />
              <SummaryCard
                label="Robustness Status"
                value={<span className={`px-3 py-1 rounded-full text-sm ${statusBadgeClass(metrics.robustness)}`}>{metrics.robustness}</span>}
              />
              <SummaryCard label="Final Answer Agreement" value={metrics.agreement} />
            </div>

            {loaded.task.analysis_error && (
              <div className="bg-rose-500/10 text-rose-200 border border-rose-500/30 rounded-xl p-4 text-sm">
                Analysis error: {loaded.task.analysis_error}
              </div>
            )}

            <div className="space-y-6">
              {families.length ? (
                families.map((family, idx) => (
                  <div key={idx} className="bg-slate-900/60 border border-white/5 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <h2 className="text-lg font-semibold text-white">{family.title}</h2>
                      <div className="text-sm text-slate-500">{family.members.length} runs</div>
                    </div>
                    {family.members.length ? (
                      (() => {
                        const rep = family.members.find((run) => run._id === family.repRunId);
                        const others = rep
                          ? family.members.filter((run) => run._id !== family.repRunId)
                          : family.members;
                        return (
                          <>
                            {rep && (
                              <RunCard run={rep} index={1} highlight label="Representative" key={rep._id || 'rep'} />
                            )}
                            {others.map((run, idxRun) => (
                              <RunCard
                                key={run._id || idxRun}
                                run={run}
                                index={rep ? idxRun + 2 : idxRun + 1}
                              />
                            ))}
                          </>
                        );
                      })()
                    ) : (
                      <p className="text-sm text-slate-500">No runs assigned to this family.</p>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-sm text-slate-500 border border-dashed border-white/10 rounded-xl p-6">
                  No reasoning families found yet.
                </div>
              )}

              {unassigned.length > 0 && (
                <div className="bg-slate-900/60 border border-white/5 rounded-2xl p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-white">Unassigned Runs</h2>
                    <div className="text-sm text-slate-500">{unassigned.length} runs</div>
                  </div>
                  <div className="space-y-4">
                    {unassigned.map((run, idx) => (
                      <RunCard key={run._id || idx} run={run} index={idx + 1} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default App;
