import React from 'react';
// `motion` is used via JSX (<motion.tr>) -- this project has no eslint-plugin-react
// installed to teach no-unused-vars that pattern.
// eslint-disable-next-line no-unused-vars
import { AnimatePresence, motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { EmptyState } from '../common/EmptyState';
import { Layers, HelpCircle } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { cn } from '../../utils/cn';

const PositionsTable = ({ positions }) => {
  const rows = Object.values(positions || {});

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 py-4">
        <Layers className="w-4 h-4 text-primary" />
        <CardTitle className="text-base">Open Positions</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {rows.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No open positions"
            description="Positions will appear here once the active run opens a trade."
            className="border-0 rounded-none"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground uppercase tracking-wider border-b border-border/50">
                  <th className="text-left font-medium px-6 py-2">Symbol</th>
                  <th className="text-right font-medium px-4 py-2">Qty</th>
                  <th className="text-right font-medium px-4 py-2">Avg Price</th>
                  <th className="text-right font-medium px-4 py-2">Realized P&amp;L</th>
                  <th className="text-right font-medium px-6 py-2">
                    <span className="inline-flex items-center gap-1 justify-end w-full">
                      Unrealized P&amp;L
                      <HelpCircle className="w-3 h-3" title="Last known value, not live mark-to-market" />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <AnimatePresence initial={false}>
                  {rows.map((p) => (
                    <motion.tr
                      key={p.symbol}
                      layout
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="border-b border-border/30 last:border-0"
                    >
                      <td className="px-6 py-3 font-mono font-medium">{p.symbol}</td>
                      <td className="px-4 py-3 text-right font-mono">{p.quantity}</td>
                      <td className="px-4 py-3 text-right font-mono">{formatCurrency(p.avg_price, 'INR')}</td>
                      <td className={cn('px-4 py-3 text-right font-mono', p.realized_pnl >= 0 ? 'text-up' : 'text-down')}>
                        {formatCurrency(p.realized_pnl, 'INR')}
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-muted-foreground">
                        {formatCurrency(p.unrealized_pnl, 'INR')}
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default PositionsTable;
