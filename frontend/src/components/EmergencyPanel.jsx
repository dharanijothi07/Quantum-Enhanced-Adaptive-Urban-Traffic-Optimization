import React from 'react';
import { Siren, Navigation, CheckCircle2, ShieldCheck, Clock } from 'lucide-react';

export default function EmergencyPanel({ state, corridorEnabled }) {
  const ambulance = state?.ambulance || {};
  const metrics = state?.metrics || {};
  const corridorActive = state?.corridor_active || [];

  const isActive = ambulance.active;
  const isFinished = ambulance.finished;
  const route = ambulance.route || [];
  const etas = ambulance.eta || {};

  return (
    <div className="bg-slate-900/90 backdrop-blur rounded-2xl border border-slate-800 p-4 shadow-xl text-slate-100 flex flex-col gap-3.5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h2 className="font-bold text-sm tracking-wide flex items-center gap-2 text-rose-300">
          <Siren className={`w-4 h-4 ${isActive ? 'text-rose-400 animate-pulse' : 'text-slate-400'}`} />
          Emergency Green Corridor
        </h2>
        <span
          className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
            isActive
              ? 'bg-rose-950/80 text-rose-300 border border-rose-500/40'
              : isFinished
              ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/40'
              : 'bg-slate-800 text-slate-400'
          }`}
        >
          {isActive ? 'IN TRANSIT' : isFinished ? 'CLEARED' : 'STANDBY'}
        </span>
      </div>

      {/* Ambulance Live Route Tracker */}
      <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-2.5 flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Navigation className="w-3.5 h-3.5 text-cyan-400" />
            <span>Target Route:</span>
          </div>
          <span className="font-mono text-cyan-300 font-bold">
            {route.length > 0 ? route.join(' → ') : 'I0 → I1 → I2 → I5'}
          </span>
        </div>

        {/* Route Steps / Nodes */}
        <div className="flex items-center justify-between gap-1 pt-1 overflow-x-auto">
          {route.map((nodeId, idx) => {
            const isCleared = (ambulance.current_node_idx || 0) > idx || isFinished;
            const isCurrent = (ambulance.current_node_idx || 0) === idx && isActive;
            const isCorridorNode = corridorActive.includes(nodeId);
            const etaVal = etas[nodeId];

            return (
              <div
                key={nodeId}
                className={`flex-1 min-w-[54px] p-1.5 rounded-lg border text-center flex flex-col items-center gap-0.5 transition ${
                  isCurrent
                    ? 'bg-rose-950/60 border-rose-500/60 text-rose-300 shadow-[0_0_8px_rgba(244,63,94,0.3)]'
                    : isCleared
                    ? 'bg-emerald-950/40 border-emerald-600/40 text-emerald-300'
                    : isCorridorNode
                    ? 'bg-pink-950/40 border-pink-500/50 text-pink-300'
                    : 'bg-slate-900 border-slate-800 text-slate-400'
                }`}
              >
                <div className="text-[11px] font-bold font-mono flex items-center gap-1">
                  {nodeId}
                  {isCleared && <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />}
                </div>
                <div className="text-[9px] font-mono text-slate-400">
                  {isCleared ? 'Passed' : etaVal !== undefined ? `${etaVal}s` : '--'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Ambulance Telemetry Cards */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="bg-slate-950/70 border border-slate-800 p-2 rounded-xl flex items-center justify-between">
          <span className="text-slate-400">Trip Elapsed:</span>
          <span className="text-slate-200 font-bold">{ambulance.elapsed || 0}s</span>
        </div>
        <div className="bg-slate-950/70 border border-slate-800 p-2 rounded-xl flex items-center justify-between">
          <span className="text-slate-400">Red Stops:</span>
          <span className="text-amber-300 font-bold">{ambulance.total_stops || 0}</span>
        </div>
      </div>

      {/* Emergency Travel Time Comparison Table */}
      <div className="flex flex-col gap-1 pt-1 border-t border-slate-800/80">
        <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
          Travel Time Across Control Methods
        </span>
        <div className="grid grid-cols-4 gap-1 text-center font-mono text-[11px]">
          {[
            { id: 'fixed', label: 'Fixed' },
            { id: 'rule_based', label: 'Rule' },
            { id: 'annealing', label: 'SA' },
            { id: 'qaoa', label: 'QAOA' }
          ].map((m) => {
            const timeVal = metrics[m.id]?.amb_time;
            const stopsVal = metrics[m.id]?.amb_stops;
            return (
              <div key={m.id} className="bg-slate-950/80 border border-slate-800 p-1.5 rounded-lg">
                <div className="text-[10px] text-slate-400">{m.label}</div>
                <div className={`font-bold ${timeVal ? 'text-cyan-300' : 'text-slate-500'}`}>
                  {timeVal ? `${timeVal}s` : '--'}
                </div>
                <div className="text-[9px] text-slate-400">{stopsVal !== undefined ? `${stopsVal} stops` : ''}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
