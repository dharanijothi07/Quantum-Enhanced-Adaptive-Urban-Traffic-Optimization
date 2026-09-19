import React, { useState, useEffect } from 'react';
import { Clock, Layers, ArrowUpRight, Fuel, Wind, Activity } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

export default function MetricsPanel({ state, viewMethod }) {
  const method = viewMethod || 'qaoa';
  const currentMetrics = state?.metrics?.[method] || {};
  const currentT = state?.t || 0;

  // Track historical rolling wait time points for sparkline
  const [historyData, setHistoryData] = useState([]);

  useEffect(() => {
    if (state?.metrics?.[method]?.rolling_avg_wait !== undefined) {
      const waitVal = state.metrics[method].rolling_avg_wait;
      setHistoryData((prev) => {
        const next = [...prev, { t: currentT, wait: waitVal }];
        return next.slice(-30); // keep last 30 data points
      });
    }
  }, [currentT, method, state]);

  return (
    <div className="bg-slate-900/90 backdrop-blur rounded-2xl border border-slate-800 p-4 shadow-xl text-slate-100 flex flex-col gap-3.5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h2 className="font-bold text-sm tracking-wide flex items-center gap-2 text-cyan-300">
          <Activity className="w-4 h-4 text-cyan-400" />
          Live Telemetry ({method.toUpperCase()})
        </h2>
        <span className="text-[11px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
          t = {currentT}s
        </span>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 gap-2.5">
        <div className="bg-slate-950/70 border border-slate-800 p-2.5 rounded-xl flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
            <Clock className="w-3.5 h-3.5 text-sky-400" />
            <span>Avg Wait Time</span>
          </div>
          <div className="text-lg font-black text-sky-300 font-mono">
            {currentMetrics.avg_wait !== undefined ? `${currentMetrics.avg_wait}s` : '0.0s'}
          </div>
          <div className="text-[10px] text-slate-400">per cleared vehicle</div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 p-2.5 rounded-xl flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span>Avg Queue</span>
          </div>
          <div className="text-lg font-black text-indigo-300 font-mono">
            {currentMetrics.avg_queue !== undefined ? `${currentMetrics.avg_queue} veh` : '0.0 veh'}
          </div>
          <div className="text-[10px] text-slate-400">Total: {currentMetrics.total_queue || 0} veh</div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 p-2.5 rounded-xl flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
            <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400" />
            <span>Throughput</span>
          </div>
          <div className="text-lg font-black text-emerald-300 font-mono">
            {currentMetrics.throughput_h !== undefined ? `${currentMetrics.throughput_h}/h` : '0/h'}
          </div>
          <div className="text-[10px] text-slate-400">Exited: {currentMetrics.total_exited || 0} veh</div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 p-2.5 rounded-xl flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
            <Fuel className="w-3.5 h-3.5 text-amber-400" />
            <span>Est. Fuel & CO2</span>
          </div>
          <div className="text-base font-bold text-amber-300 font-mono flex items-baseline gap-1">
            <span>{currentMetrics.fuel_l || 0}L</span>
            <span className="text-xs text-slate-400">({currentMetrics.co2_kg || 0}kg)</span>
          </div>
          <div className="text-[9px] text-slate-400">*estimated baseline model</div>
        </div>
      </div>

      {/* Rolling 60s Sparkline */}
      <div className="flex flex-col gap-1 pt-1 border-t border-slate-800/80">
        <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
          Rolling 60s Waiting Time Trend
        </span>
        <div className="w-full h-20 bg-slate-950/80 rounded-xl p-1 border border-slate-800/80">
          {historyData.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={historyData} margin={{ top: 4, right: 4, left: -25, bottom: 0 }}>
                <defs>
                  <linearGradient id="waitGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <YAxis stroke="#64748b" tick={{ fontSize: 9 }} domain={['dataMin - 1', 'dataMax + 1']} />
                <Tooltip
                  content={({ payload }) => {
                    if (payload && payload.length) {
                      return (
                        <div className="bg-slate-900 border border-slate-700 px-2 py-1 rounded text-[10px] font-mono text-cyan-300">
                          {payload[0].value.toFixed(1)}s wait
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area type="monotone" dataKey="wait" stroke="#38bdf8" strokeWidth={2} fill="url(#waitGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[11px] text-slate-400">
              Gathering telemetry stream...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
