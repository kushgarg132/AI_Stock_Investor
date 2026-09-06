import React from 'react';
import { Sheet, Money, NetLine, Ruling } from '../doc/Doc';
import { formatCurrency, formatPercent, formatQuantity, formatNoteDate } from '../../utils/formatters';
import { cn } from '../../utils/cn';

/**
 * The statement's summary blocks.
 *
 * Deliberately not a row of metric tiles: a statement states its lines and
 * closes them under a double rule, and the net is the only figure that gets
 * to be large. Reading a P&L should feel like reading a total, not scanning
 * four competing badges.
 */

const Line = ({ label, children, muted }) => (
  <div className="flex items-baseline justify-between gap-4 py-1.5">
    <span className={cn('text-sm', muted ? 'text-[var(--ink-faint)]' : 'text-[var(--ink-soft)]')}>
      {label}
    </span>
    <span className="figure-md text-sm tabular-nums">{children}</span>
  </div>
);

const PnlStatement = ({ pnl, loading }) => {
  if (loading || !pnl) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <Sheet title="Today">
          <Ruling rows={4} />
        </Sheet>
        <Sheet title="Month to date">
          <Ruling rows={4} />
        </Sheet>
      </div>
    );
  }

  const { today, month, open } = pnl;
  const netToday = (today.realized || 0) + (today.unrealized || 0);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Sheet title="Today" meta={formatNoteDate()}>
        <Line label="Realised">
          <Money value={today.realized} />
        </Line>
        <Line label="Unrealised, marked to market">
          <Money value={today.unrealized} />
        </Line>
        <Line label="Round trips closed" muted>
          {formatQuantity(today.trades)}
          {today.trades > 0 && (
            <span className="text-[var(--ink-faint)]">
              {' '}
              ({today.wins}W / {today.losses}L)
            </span>
          )}
        </Line>
        <Line label="Turnover" muted>
          {formatCurrency(today.turnover)}
        </Line>

        <NetLine label="Net today">
          <Money value={netToday} size="lg" />
        </NetLine>
      </Sheet>

      <Sheet title="Month to date">
        <Line label="Realised">
          <Money value={month.realized} />
        </Line>
        <Line label="Round trips closed" muted>
          {formatQuantity(month.trades)}
        </Line>
        <Line label="Strike rate" muted>
          {month.trades ? formatPercent(month.win_rate * 100) : '—'}
        </Line>
        <Line label="Best / worst">
          <span className="text-up">{month.trades ? <Money value={month.best} /> : '—'}</span>
          <span className="text-[var(--ink-faint)]"> / </span>
          <span className="text-down">{month.trades ? <Money value={month.worst} /> : '—'}</span>
        </Line>

        <NetLine label={`Open exposure · ${formatQuantity(open.positions)} scrip`}>
          <span className="figure-md text-base">{formatCurrency(open.exposure)}</span>
        </NetLine>
      </Sheet>
    </div>
  );
};

export default PnlStatement;
