import React from 'react';
import { Cpu, Atom, Clock, CheckCircle2, AlertCircle, Info } from 'lucide-react';

export default function SolverPanel({ state }) {
  const solver = state?.solver || {};
  const isFallback = solver.fallback_used;

  return (
    <div className="bg-slate-900/90 backdrop-blur rounded-2xl border border-slate-800 p-4 shadow-xl text-slate-100 flex flex-col gap-3.5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h2 className="font-bold text-sm tracking-wide flex items-center gap-2 text-cyan-300">
          <Atom className="w-4 h-4 text-cyan-400 animate-spin" style={{ animationDuration: '8s' }} />
          QAOA Quantum Solver Metrics
        </h2>
        <span className="text-[10px] font-mono text-slate-300 bg-cyan-950/80 border border-cyan-500/40 px-2 py-0.5 rounded">
          {solver.backend_used?.toUpperCase() || 'QISKIT'} AER
        </span>
      </div>

      {/* Solver Specs Grid */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-slate-950/70 border border-slate-800 p-2 rounded-xl">
          <div className="text-[10px] text-slate-400 font-mono">QUBITS</div>
          <div className="text-base font-extrabold text-cyan-300 font-mono">
            {solver.qubits || 18}
          </div>
          <div className="text-[9px] text-slate-400">6 Int x 3 Slots</div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 p-2 rounded-xl">
          <div className="text-[10px] text-slate-400 font-mono">ANSATZ DEPTH</div>
          <div className="text-base font-extrabold text-indigo-300 font-mono">
            p = {solver.p || 2}
          </div>
          <div className="text-[9px] text-slate-400">4 parameters</div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 p-2 rounded-xl">
          <div className="text-[10px] text-slate-400 font-mono">OPTIMIZER</div>
          <div className="text-base font-extrabold text-emerald-300 font-mono">
            {solver.iters || 0}
          </div>
          <div className="text-[9px] text-slate-400">COBYLA iters</div>
        </div>
      </div>

      {/* Real Optimization Costs & Optimality Gap */}
      <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-2.5 flex flex-col gap-1.5 text-xs font-mono">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Wall Solve Time:</span>
          <span className="text-slate-200 font-bold">{solver.wall_time_s || 0.0}s</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">QAOA Best Cost:</span>
          <span className="text-cyan-300 font-bold">{solver.best_cost !== undefined ? solver.best_cost : '--'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Exact Global Optimum:</span>
          <span className="text-emerald-400 font-bold">{solver.exact_cost !== undefined ? solver.exact_cost : '--'}</span>
        </div>
        <div className="flex items-center justify-between pt-1 border-t border-slate-800">
          <span className="text-slate-400">Optimality Gap:</span>
          <span className="text-amber-300 font-extrabold">
            {solver.gap !== undefined ? `${(solver.gap * 100).toFixed(2)}%` : '0.00%'}
          </span>
        </div>
      </div>

      {/* Fallback & Health Indicators */}
      <div className="flex items-center justify-between text-[11px] px-1 text-slate-300">
        <div className="flex items-center gap-1.5">
          {isFallback ? (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-amber-300">SA Fallback Active</span>
            </>
          ) : (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-300">Quantum QAOA Active</span>
            </>
          )}
        </div>
        <div className="text-slate-400 font-mono">Late Solves: {solver.late_solves || 0}</div>
      </div>

      {/* Quantum Scope Clarification Banner */}
      <div className="bg-gradient-to-r from-cyan-950/40 to-indigo-950/40 border border-cyan-800/40 rounded-xl p-2.5 text-[11px] text-slate-300 flex items-start gap-2">
        <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-cyan-200">Where is Quantum Used? </span>
          Only the 10s signal-timing decision step is formulated as a QUBO and solved via QAOA statevector simulation. All queue dynamics and events are classical.
        </div>
      </div>
    </div>
  );
}
