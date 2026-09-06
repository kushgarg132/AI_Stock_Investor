import React from 'react';
import { Sheet, Field } from '../doc/Doc';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import { cn } from '../../utils/cn';

const RISK_TONE = {
  low: 'text-up',
  medium: 'text-[var(--stamp)]',
  high: 'text-down',
};

const RiskPanel = ({ signal, risk, currency }) => {
  const ratio =
    signal?.target_price && signal?.stop_loss && signal?.entry_price
      ? Math.abs(
          (signal.target_price - signal.entry_price) / (signal.entry_price - signal.stop_loss)
        )
      : null;
  const level = risk?.risk_level;

  return (
    <Sheet title="Risk" className="h-full">
      <div className="grid grid-cols-2 gap-4 pb-3 border-b border-[var(--rule)]">
        <div>
          <p className="field-label mb-1">Assessment</p>
          <p
            className={cn(
              'font-[family-name:var(--font-narrow)] font-bold uppercase tracking-[0.11em]',
              RISK_TONE[level?.toLowerCase()] || 'text-[var(--ink-soft)]'
            )}
          >
            {level || '—'}
          </p>
        </div>
        <Field
          label="Volatility"
          value={
            risk?.volatility_score ? formatPercent(risk.volatility_score * 100) : '—'
          }
        />
      </div>

      {signal ? (
        <div className="grid grid-cols-3 gap-3 py-3 border-b border-[var(--rule)]">
          <Field label="Entry" value={formatCurrency(signal.entry_price, currency)} />
          <Field label="Stop" value={formatCurrency(signal.stop_loss, currency)} tone="down" />
          <Field label="Target" value={formatCurrency(signal.target_price, currency)} tone="up" />
        </div>
      ) : (
        <p className="py-3 border-b border-[var(--rule)] text-sm text-[var(--ink-soft)]">
          No trade levels were proposed for this scrip.
        </p>
      )}

      <div className="pt-3 flex items-baseline justify-between gap-3">
        <span className="field-label">Risk / reward</span>
        <span className="figure-md text-base">{ratio ? `1 : ${ratio.toFixed(2)}` : '—'}</span>
      </div>
    </Sheet>
  );
};

export default RiskPanel;
