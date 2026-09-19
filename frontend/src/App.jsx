import React, { useState, useEffect, useRef } from 'react';
import { useSocket } from './useSocket';
import { fetchNetwork, fetchHealth, fetchReplayData } from './api';

import ControlBar from './components/ControlBar';
import MapView from './components/MapView';
import EventPanel from './components/EventPanel';
import MetricsPanel from './components/MetricsPanel';
import ComparisonPanel from './components/ComparisonPanel';
import SolverPanel from './components/SolverPanel';
import EmergencyPanel from './components/EmergencyPanel';

export default function App() {
  const { latestState, setLatestState, connected, isReplaying, setIsReplaying } = useSocket();
  const [network, setNetwork] = useState(null);
  const [health, setHealth] = useState(null);

  // Replay playback state
  const [replayFrames, setReplayFrames] = useState([]);
  const [replayIdx, setReplayIdx] = useState(0);
  const replayTimerRef = useRef(null);

  // Load initial network topography & health
  useEffect(() => {
    fetchNetwork().then(setNetwork);
    fetchHealth().then(setHealth);
  }, []);

  // Replay Mode handler
  const toggleReplay = async () => {
    if (!isReplaying) {
      const frames = await fetchReplayData();
      if (frames && frames.length > 0) {
        setReplayFrames(frames);
        setReplayIdx(0);
        setIsReplaying(true);
        setLatestState(frames[0]);
      } else {
        alert('No replay trace found in public/replay.json');
      }
    } else {
      setIsReplaying(false);
      if (replayTimerRef.current) clearInterval(replayTimerRef.current);
    }
  };

  // Replay playback ticker
  useEffect(() => {
    if (isReplaying && replayFrames.length > 0) {
      replayTimerRef.current = setInterval(() => {
        setReplayIdx((prev) => {
          const next = (prev + 1) % replayFrames.length;
          setLatestState(replayFrames[next]);
          return next;
        });
      }, 500);
      return () => clearInterval(replayTimerRef.current);
    }
  }, [isReplaying, replayFrames, setLatestState]);

  // Active state to render
  const currentState = latestState;
  const running = currentState?.running || false;
  const speed = 3;
  const seed = currentState?.seed || 42;
  const viewMethod = currentState?.view_method || 'qaoa';
  const corridorEnabled = currentState?.corridor_enabled ?? true;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-slate-950">
      {/* 1. Global Navigation & Control Bar */}
      <ControlBar
        running={running}
        speed={speed}
        seed={seed}
        viewMethod={viewMethod}
        corridorEnabled={corridorEnabled}
        connected={connected}
        isReplaying={isReplaying}
        onToggleReplay={toggleReplay}
        onUpdateState={setLatestState}
      />

      {/* 2. Main Dashboard Body */}
      <main className="flex-1 p-4 max-w-[1680px] w-full mx-auto flex flex-col gap-4">
        {/* Top Split Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left Column: MapView (7 / 12) */}
          <div className="lg:col-span-7 flex flex-col gap-3">
            <div className="flex items-center justify-between px-1">
              <div className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                <span>Active City Grid: <strong className="text-cyan-300 uppercase">{viewMethod}</strong></span>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                6 Signalized Intersections (2x3 Grid)
              </span>
            </div>
            <MapView network={network} state={currentState} />
            <EventPanel network={network} state={currentState} isReplaying={isReplaying} />
          </div>

          {/* Right Column: Stacked KPI & Solver Telemetry (5 / 12) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            <MetricsPanel state={currentState} viewMethod={viewMethod} />
            <SolverPanel state={currentState} />
            <EmergencyPanel state={currentState} corridorEnabled={corridorEnabled} />
          </div>
        </div>

        {/* Bottom Section: Multi-Method Comparison & Benchmark Table */}
        <ComparisonPanel state={currentState} />
      </main>

      {/* 3. Footer */}
      <footer className="bg-slate-950 border-t border-slate-900 px-4 py-2 text-center text-xs text-slate-500 font-mono flex items-center justify-between">
        <div>QuantumFlow v1.0.0 &bull; Hybrid QAOA Urban Traffic Optimization Platform</div>
        <div>Simulated on Qiskit Aer &bull; Classical Macroscopic Queue Model</div>
      </footer>
    </div>
  );
}
