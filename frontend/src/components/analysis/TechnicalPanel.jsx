import React from 'react';
import { Sheet, Statement, Row, Cell, Empty } from '../doc/Doc';
import { Badge } from '../common/Badge';
import { formatCurrency } from '../../utils/formatters';

const rsiReading = (rsi) => {
  if (typeof rsi !== 'number') return '—';
  if (rsi > 70) return 'Overbought';
  if (rsi < 30) return 'Oversold';
  return 'Neutral';
};

const TechnicalPanel = ({ signals, indicators, currency }) => {
  const readings = indicators
    ? [
        ['RSI (14)', typeof indicators.rsi === 'number' ? indicators.rsi.toFixed(2) : '—', rsiReading(indicators.rsi)],
        [
          'MACD histogram',
          typeof indicators.macd?.histogram === 'number' ? indicators.macd.histogram.toFixed(2) : '—',
          typeof indicators.macd?.histogram !== 'number'
            ? '—'
            : indicators.macd.histogram > 0
              ? 'Bullish'
              : 'Bearish',
        ],
        ['SMA 200', formatCurrency(indicators.sma_200, currency), 'Trend'],
        ['ATR', typeof indicators.atr === 'number' ? indicators.atr.toFixed(2) : '—', 'Volatility'],
      ]
    : [];

  return (
    <Sheet title="Technicals" className="h-full">
      {readings.length > 0 && (
        <Statement
          columns={[
            { key: 'measure', label: 'Measure' },
            { key: 'value', label: 'Value', align: 'right' },
            { key: 'reading', label: 'Reading', align: 'right' },
          ]}
        >
          {readings.map(([label, value, reading]) => (
            <Row key={label}>
              <Cell className="text-[var(--ink-soft)]">{label}</Cell>
              <Cell align="right" mono>
                {value}
              </Cell>
              <Cell align="right" className="doc-meta normal-case">
                {reading}
              </Cell>
            </Row>
          ))}
        </Statement>
      )}

      <div className="mt-4">
        <p className="field-label mb-2">Signals</p>
        {signals && signals.length > 0 ? (
          <ul className="space-y-1.5">
            {signals.slice(0, 4).map((signal, index) => (
              <li
                key={`${signal.signal || signal.indicator}-${index}`}
                className="flex items-center justify-between gap-3 py-1.5 border-b border-[var(--rule)] last:border-b-0"
              >
                <span className="text-sm truncate">{signal.signal || signal.indicator}</span>
                <Badge
                  variant={
                    signal.action === 'buy'
                      ? 'success'
                      : signal.action === 'sell'
                        ? 'destructive'
                        : 'secondary'
                  }
                >
                  {signal.action}
                </Badge>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-[var(--ink-soft)]">No signal is firing on this scrip.</p>
        )}
      </div>
    </Sheet>
  );
};

export default TechnicalPanel;
