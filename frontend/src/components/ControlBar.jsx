import React from 'react';
import { Play, Pause, RotateCcw, Zap, ShieldAlert, Radio, Film } from 'lucide-react';
import { sendControl } from '../api';

export default function ControlBar({
  running,
  speed,
  seed,
  viewMethod,
  corridorEnabled,
  connected,
  isReplaying,
  onToggleReplay,
  onUpdateState
}) {
  const handleAction = async (action) => {
    if (isReplaying) return;
    const res = await sendControl({
      action,
      seed: parseInt(seed, 10),
      speed: parseFloat(speed),
      view_method: viewMethod,
      corridor_enabled: corridorEnabled
    });
    if (res && onUpdateState) {
      onUpdateState(res);
    }
  };

  const handleMethodChange = async (method) => {
    if (isReplaying) return;
    await sendControl({
      action: running ? 'start' : 'pause',
      seed: parseInt(seed, 10),
      speed: parseFloat(speed),
      view_method: method,
      corridor_enabled: corridorEnabled
    });
  };

  const handleSpeedChange = async (e) => {
    const newSpeed = parseFloat(e.target.value);
    if (isReplaying) return;
    await sendControl({
      action: running ? 'start' : 'pause',
      seed: parseInt(seed, 10),
      speed: newSpeed,
      view_method: viewMethod,
      corridor_enabled: corridorEnabled
    });
  };

  const handleCorridorToggle = async () => {
    const nextVal = !corridorEnabled;
    if (isReplaying) return;
    await sendControl({
      action: running ? 'start' : 'pause',
      seed: parseInt(seed, 10),
      speed: parseFloat(speed),
      view_method: viewMethod,
      corridor_enabled: nextVal
    });
  };

  return (
    <header className="bg-slate-900/90 backdrop-blur border-b border-slate-800 px-4 py-3 sticky top-0 z-50 flex flex-wrap items-center justify-between gap-3 text-slate-100 shadow-md">
      {/* Brand & Connection Status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-cyan-500/20">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-cyan-400 via-sky-200 to-indigo-400 bg-clip-text text-transparent">
              QuantumFlow
            </h1>
            <div className="text-[10px] text-slate-400 font-mono flex items-center gap-1.5">
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  isReplaying
                    ? 'bg-amber-400 animate-pulse'
                    : connected
                    ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                    : 'bg-rose-500'
                }`}
              />
              {isReplaying ? 'REPLAY MODE' : connected ? 'LIVE ENGINE' : 'CONNECTING...'}
            </div>
          </div>
        </div>
      </div>

      {/* Primary Simulation Controls */}
      <div className="flex items-center gap-2 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 shadow-inner">
        <button
          onClick={() => handleAction(running ? 'pause' : 'start')}
          disabled={isReplaying}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg font-semibold text-xs transition shadow-sm ${
            running
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30'
              : 'bg-emerald-500 text-slate-950 hover:bg-emerald-400'
          } ${isReplaying ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {running ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current" />}
          {running ? 'Pause' : 'Start'}
        </button>

        <button
          onClick={() => handleAction('reset')}
          disabled={isReplaying}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-700/70 transition"
          title="Reset Simulation"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset</span>
        </button>

        {/* Speed Selector */}
        <div className="flex items-center gap-1 pl-2 border-l border-slate-700 text-xs text-slate-300">
          <span className="text-[11px] text-slate-400 font-mono">Speed:</span>
          <select
            value={speed}
            onChange={handleSpeedChange}
            disabled={isReplaying}
            className="bg-slate-900 border border-slate-700 text-xs text-cyan-300 font-semibold rounded px-1.5 py-1 focus:outline-none focus:border-cyan-500"
          >
            <option value="1">1x</option>
            <option value="2">2x</option>
            <option value="3">3x</option>
            <option value="5">5x</option>
            <option value="10">10x</option>
          </select>
        </div>

        {/* Seed Input */}
        <div className="flex items-center gap-1 pl-2 border-l border-slate-700 text-xs text-slate-300">
          <span className="text-[11px] text-slate-400 font-mono">Seed:</span>
          <input
            type="number"
            value={seed}
            disabled={isReplaying}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10) || 42;
              handleAction('reset', val);
            }}
            className="w-14 bg-slate-900 border border-slate-700 text-xs text-slate-200 font-mono rounded px-1.5 py-1 focus:outline-none focus:border-cyan-500 text-center"
          />
        </div>
      </div>

      {/* Map Method Tabs */}
      <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60">
        <span className="text-[10px] uppercase font-bold text-slate-400 px-2 tracking-wider">Map View:</span>
        {[
          { id: 'fixed', label: 'Fixed' },
          { id: 'rule_based', label: 'Rule-Based' },
          { id: 'annealing', label: 'Simulated Anneal' },
          { id: 'qaoa', label: 'QAOA (Quantum)' }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleMethodChange(tab.id)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
              viewMethod === tab.id
                ? tab.id === 'qaoa'
                  ? 'bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-md shadow-cyan-500/20'
                  : 'bg-slate-700 text-cyan-300 border border-slate-600'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Emergency Toggle & Replay Mode */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleCorridorToggle}
          disabled={isReplaying}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition shadow-sm ${
            corridorEnabled
              ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
              : 'bg-slate-800/80 border-slate-700 text-slate-400'
          }`}
        >
          <ShieldAlert className={`w-3.5 h-3.5 ${corridorEnabled ? 'text-emerald-400 animate-pulse' : ''}`} />
          <span>Corridor: {corridorEnabled ? 'ON' : 'OFF'}</span>
        </button>

        <button
          onClick={onToggleReplay}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-xl border text-xs font-semibold transition ${
            isReplaying
              ? 'bg-amber-500 text-slate-950 border-amber-400 shadow-md shadow-amber-500/30'
              : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'
          }`}
        >
          <Film className="w-3.5 h-3.5" />
          <span>{isReplaying ? 'Exit Replay' : 'Replay Trace'}</span>
        </button>
      </div>
    </header>
  );
}
