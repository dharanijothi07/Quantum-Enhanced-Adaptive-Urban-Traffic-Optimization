import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { BarChart3, TrendingUp, Award, Table } from 'lucide-react';
import { fetchLatestBenchmark } from '../api';

export default function ComparisonPanel({ state }) {
  const [benchmarkData, setBenchmarkData] = useState(null);
  const metrics = state?.metrics || {};

  useEffect(() => {
    fetchLatestBenchmark().then((data) => {
      if (data && data.methods) setBenchmarkData(data);
    });
  }, []);

  const fixedWait = metrics.fixed?.avg_wait || 1;
  const fixedQueue = metrics.fixed?.avg_queue || 1;
  const fixedThru = metrics.fixed?.throughput_h || 1;
  const fixedFuel = metrics.fixed?.fuel_l || 1;

  // Chart data from live simulation
  const chartData = [
    {
      name: 'Fixed Time',
      wait: metrics.fixed?.avg_wait || 0,
      queue: metrics.fixed?.avg_queue || 0,
      throughput: (metrics.fixed?.throughput_h || 0) / 100, // scaled for chart
      fuel: metrics.fixed?.fuel_l || 0
    },
    {
      name: 'Rule-Based',
      wait: metrics.rule_based?.avg_wait || 0,
      queue: metrics.rule_based?.avg_queue || 0,
      throughput: (metrics.rule_based?.throughput_h || 0) / 100,
      fuel: metrics.rule_based?.fuel_l || 0
    },
    {
      name: 'Simulated Anneal',
      wait: metrics.annealing?.avg_wait || 0,
      queue: metrics.annealing?.avg_queue || 0,
      throughput: (metrics.annealing?.throughput_h || 0) / 100,
      fuel: metrics.annealing?.fuel_l || 0
    },
    {
      name: 'QAOA (Quantum)',
      wait: metrics.qaoa?.avg_wait || 0,
      queue: metrics.qaoa?.avg_queue || 0,
      throughput: (metrics.qaoa?.throughput_h || 0) / 100,
      fuel: metrics.qaoa?.fuel_l || 0
    }
  ];

  // Compute live % improvements vs Fixed
  const qaoaWaitImp = (((fixedWait - (metrics.qaoa?.avg_wait || 0)) / Math.max(1e-3, fixedWait)) * 100).toFixed(1);
  const qaoaQueueImp = (((fixedQueue - (metrics.qaoa?.avg_queue || 0)) / Math.max(1e-3, fixedQueue)) * 100).toFixed(1);
  const qaoaThruImp = ((((metrics.qaoa?.throughput_h || 0) - fixedThru) / Math.max(1e-3, fixedThru)) * 100).toFixed(1);

  return (
    <div className="bg-slate-900/90 backdrop-blur rounded-2xl border border-slate-800 p-4 shadow-xl text-slate-100 flex flex-col gap-4">
      {/* Header & Badges */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-indigo-400" />
          <h2 className="font-bold text-sm tracking-wide text-cyan-300">
            Multi-Method Performance Benchmarking
          </h2>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 px-2.5 py-1 rounded-lg font-bold">
            QAOA Wait: {qaoaWaitImp > 0 ? `+${qaoaWaitImp}%` : `${qaoaWaitImp}%`}
          </span>
          <span className="bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 px-2.5 py-1 rounded-lg font-bold">
            QAOA Throughput: {qaoaThruImp > 0 ? `+${qaoaThruImp}%` : `${qaoaThruImp}%`}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Live Recharts Grouped Comparison */}
        <div className="lg:col-span-7 bg-slate-950/70 border border-slate-800 rounded-xl p-3 flex flex-col gap-2">
          <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
            <span>Live Stream Comparison (All 4 Methods)</span>
            <span className="text-[10px] text-slate-400 font-mono">*Throughput /100</span>
          </div>
          <div className="w-full h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 10 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar dataKey="wait" name="Wait Time (s)" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="queue" name="Avg Queue (veh)" fill="#818cf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="throughput" name="Throughput (/100)" fill="#34d399" radius={[4, 4, 0, 0]} />
                <Bar dataKey="fuel" name="Fuel (L)" fill="#fbbf24" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Multi-Seed Offline Benchmark Aggregates Table */}
        <div className="lg:col-span-5 bg-slate-950/70 border border-slate-800 rounded-xl p-3 flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
            <span className="flex items-center gap-1.5">
              <Table className="w-3.5 h-3.5 text-cyan-400" />
              Benchmark Table ({benchmarkData?.metadata?.num_seeds || 'N'} seeds, {benchmarkData?.metadata?.duration_s || '600'}s)
            </span>
          </div>

          <div className="overflow-x-auto text-[11px] font-mono">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[10px]">
                  <th className="py-1">METHOD</th>
                  <th className="py-1">WAIT (s)</th>
                  <th className="py-1">QUEUE</th>
                  <th className="py-1">IMPRV.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {['fixed', 'rule_based', 'annealing', 'qaoa'].map((mKey) => {
                  const bMethod = benchmarkData?.methods?.[mKey];
                  const isQ = mKey === 'qaoa';
                  return (
                    <tr key={mKey} className={isQ ? 'bg-cyan-950/30 text-cyan-200' : 'text-slate-300'}>
                      <td className="py-1 font-bold capitalize">{mKey.replace('_', ' ')}</td>
                      <td className="py-1">
                        {bMethod ? `${bMethod.avg_wait?.mean} ± ${bMethod.avg_wait?.std}` : '--'}
                      </td>
                      <td className="py-1">
                        {bMethod ? `${bMethod.avg_queue?.mean}` : '--'}
                      </td>
                      <td className="py-1 font-bold text-emerald-400">
                        {bMethod?.pct_improvement?.wait_time_pct ? `+${bMethod.pct_improvement.wait_time_pct}%` : '0%'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {benchmarkData?.qaoa_summary && (
            <div className="mt-auto pt-2 border-t border-slate-800 text-[10px] text-slate-400 flex items-center justify-between">
              <span>QAOA Opt Gap: <strong className="text-cyan-300">{benchmarkData.qaoa_summary.mean_optimality_gap}</strong></span>
              <span>Mean Solve: <strong className="text-slate-200">{benchmarkData.qaoa_summary.mean_wall_time_s}s</strong></span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
