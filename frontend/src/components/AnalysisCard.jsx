import React from 'react';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';

const AnalysisCard = ({ data }) => {
  if (!data) return null;

  const { decision, reasoning, analyst_summary, quant_signals_count, final_signal } = data;

  const getDecisionColor = (d) => {
    switch (d) {
      case 'BUY': return 'text-green-400 border-green-500/30 bg-green-500/10';
      case 'SELL': return 'text-red-400 border-red-500/30 bg-red-500/10';
      default: return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
    }
  };

  const getIcon = (d) => {
    switch (d) {
      case 'BUY': return <TrendingUp className="w-8 h-8" />;
      case 'SELL': return <TrendingDown className="w-8 h-8" />;
      default: return <Minus className="w-8 h-8" />;
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Main Decision Card */}
      <div className={clsx(
        "md:col-span-3 p-6 rounded-2xl border backdrop-blur-sm",
        getDecisionColor(decision)
      )}>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider opacity-80">Final Decision</h2>
            <div className="flex items-center gap-3 mt-1">
              {getIcon(decision)}
              <span className="text-4xl font-bold">{decision}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm opacity-60">Confidence Score</div>
            <div className="text-2xl font-bold">High</div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-white/10">
          <p className="text-lg leading-relaxed opacity-90">{reasoning}</p>
        </div>
      </div>

      {/* Analyst Summary */}
      <div className="p-6 rounded-2xl bg-slate-800/50 border border-slate-700 backdrop-blur-sm">
        <div className="flex items-center gap-2 mb-4 text-blue-400">
          <CheckCircle className="w-5 h-5" />
          <h3 className="font-semibold">Fundamental Analysis</h3>
        </div>
        <p className="text-slate-300 text-sm leading-relaxed">
          {analyst_summary || "No summary available."}
        </p>
      </div>

      {/* Technical Signals */}
      <div className="p-6 rounded-2xl bg-slate-800/50 border border-slate-700 backdrop-blur-sm">
        <div className="flex items-center gap-2 mb-4 text-purple-400">
          <TrendingUp className="w-5 h-5" />
          <h3 className="font-semibold">Technical Signals</h3>
        </div>
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Active Signals</span>
            <span className="text-xl font-bold text-white">{quant_signals_count}</span>
          </div>
          {final_signal && (
            <div className="p-3 rounded-lg bg-slate-700/50 border border-slate-600">
              <div className="text-xs text-slate-400 mb-1">Primary Signal</div>
              <div className="font-medium text-white">{final_signal.strategy}</div>
              <div className="text-sm text-slate-300 mt-1">
                Entry: <span className="text-white font-mono">${final_signal.entry_price}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Risk Assessment */}
      <div className="p-6 rounded-2xl bg-slate-800/50 border border-slate-700 backdrop-blur-sm">
        <div className="flex items-center gap-2 mb-4 text-orange-400">
          <AlertTriangle className="w-5 h-5" />
          <h3 className="font-semibold">Risk Assessment</h3>
        </div>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
             <span className="text-slate-400">Stop Loss</span>
             <span className="text-red-400 font-mono">
               ${final_signal?.stop_loss || '---'}
             </span>
          </div>
          <div className="flex justify-between text-sm">
             <span className="text-slate-400">Take Profit</span>
             <span className="text-green-400 font-mono">
               ${final_signal?.take_profit || '---'}
             </span>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-700">
             <div className="text-xs text-slate-500">Risk/Reward Ratio</div>
             <div className="text-lg font-bold text-white">
               {final_signal ? '1:2.5' : '---'}
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalysisCard;
