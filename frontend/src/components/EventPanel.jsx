import React, { useState } from 'react';
import { Flame, AlertTriangle, Ban, Siren, Clock } from 'lucide-react';
import { sendEvent } from '../api';

export default function EventPanel({ network, state, isReplaying }) {
  const [selectedLink, setSelectedLink] = useState('L_B_ENTRY_I0_W_I0');
  const [surgeFactor, setSurgeFactor] = useState(2.5);
  const [eventDuration, setEventDuration] = useState(60);
  const [ambOrigin, setAmbOrigin] = useState('B_ENTRY_I0_W');
  const [ambDest, setAmbDest] = useState('B_EXIT_I5_E');

  const links = network?.links || {};
  const activeEvents = state?.events || [];
  const currentT = state?.t || 0;

  const handleTrigger = async (type) => {
    if (isReplaying) return;
    await sendEvent({
      type,
      link_id: type === 'ambulance' ? undefined : selectedLink,
      factor: type === 'surge' ? parseFloat(surgeFactor) : undefined,
      duration_s: parseInt(eventDuration, 10),
      origin: type === 'ambulance' ? ambOrigin : undefined,
      destination: type === 'ambulance' ? ambDest : undefined
    });
  };

  return (
    <div className="bg-slate-900/90 backdrop-blur rounded-2xl border border-slate-800 p-4 shadow-xl text-slate-100 flex flex-col gap-3.5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h2 className="font-bold text-sm tracking-wide flex items-center gap-2 text-cyan-300">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          Live Event Injection
        </h2>
        <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
          Active: {activeEvents.length}
        </span>
      </div>

      {/* Target Link Selector */}
      <div className="flex flex-col gap-1 text-xs">
        <label className="text-slate-400 font-mono text-[11px]">Target Link:</label>
        <select
          value={selectedLink}
          onChange={(e) => setSelectedLink(e.target.value)}
          disabled={isReplaying}
          className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg p-2 focus:outline-none focus:border-cyan-500 font-mono"
        >
          {Object.keys(links).map((lId) => (
            <option key={lId} value={lId}>
              {lId} ({links[lId].orientation} - {links[lId].from_node} → {links[lId].to_node})
            </option>
          ))}
        </select>
      </div>

      {/* Action Trigger Buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => handleTrigger('surge')}
          disabled={isReplaying}
          className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-semibold transition"
        >
          <Flame className="w-3.5 h-3.5 text-amber-400" />
          <span>Traffic Surge</span>
        </button>

        <button
          onClick={() => handleTrigger('accident')}
          disabled={isReplaying}
          className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold transition"
        >
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
          <span>Accident Block</span>
        </button>

        <button
          onClick={() => handleTrigger('closure')}
          disabled={isReplaying}
          className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold transition"
        >
          <Ban className="w-3.5 h-3.5 text-slate-400" />
          <span>Road Closure</span>
        </button>

        <button
          onClick={() => handleTrigger('ambulance')}
          disabled={isReplaying}
          className="flex items-center justify-center gap-1.5 p-2 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/40 text-xs font-semibold transition shadow-sm"
        >
          <Siren className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span>Dispatch Ambulance</span>
        </button>
      </div>

      {/* Active Events Monitor */}
      {activeEvents.length > 0 && (
        <div className="mt-1 flex flex-col gap-1.5 pt-2 border-t border-slate-800/80">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Active Disruptions</span>
          <div className="flex flex-col gap-1 max-h-28 overflow-y-auto pr-1">
            {activeEvents.map((ev) => {
              const rem = Math.max(0, ev.until - currentT);
              return (
                <div
                  key={ev.id || ev.type + ev.until}
                  className="bg-slate-950/70 border border-slate-800 rounded-lg p-1.5 text-[11px] flex items-center justify-between"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
                    <span className="font-semibold capitalize text-amber-300">{ev.type}</span>
                    <span className="text-slate-400 font-mono text-[10px]">{ev.link_id || 'Grid'}</span>
                  </div>
                  <div className="flex items-center gap-1 text-slate-400 font-mono text-[10px]">
                    <Clock className="w-3 h-3" />
                    <span>{rem}s left</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
