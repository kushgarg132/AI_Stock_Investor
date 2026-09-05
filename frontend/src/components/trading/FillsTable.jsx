import React, { useState } from 'react';
// `motion` is used via JSX (<motion.tr>) -- this project has no eslint-plugin-react
// installed to teach no-unused-vars that pattern.
// eslint-disable-next-line no-unused-vars
import { AnimatePresence, motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { EmptyState } from '../common/EmptyState';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Receipt } from 'lucide-react';
import { formatCurrency, formatTimeAgo } from '../../utils/formatters';

const PAGE_SIZE = 50;

const FillsTable = ({ fills }) => {
  const [visible, setVisible] = useState(PAGE_SIZE);
  const sorted = [...(fills || [])].sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  );
  const rows = sorted.slice(0, visible);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 py-4">
        <Receipt className="w-4 h-4 text-primary" />
        <CardTitle className="text-base">Fills</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {rows.length === 0 ? (
          <EmptyState
            icon={Receipt}
            title="No fills yet"
            description="Executed orders will appear here as the active run trades."
            className="border-0 rounded-none"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground uppercase tracking-wider border-b border-border/50">
                    <th className="text-left font-medium px-6 py-2">Time</th>
                    <th className="text-left font-medium px-4 py-2">Symbol</th>
                    <th className="text-left font-medium px-4 py-2">Side</th>
                    <th className="text-right font-medium px-4 py-2">Qty</th>
                    <th className="text-right font-medium px-4 py-2">Price</th>
                    <th className="text-right font-medium px-6 py-2">Costs</th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence initial={false}>
                    {rows.map((f) => (
                      <motion.tr
                        key={f.order_id}
                        layout
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="border-b border-border/30 last:border-0"
                      >
                        <td className="px-6 py-3 text-muted-foreground" title={new Date(f.timestamp).toLocaleString()}>
                          {formatTimeAgo(f.timestamp)}
                        </td>
                        <td className="px-4 py-3 font-mono font-medium">{f.symbol}</td>
                        <td className="px-4 py-3">
                          <Badge variant={f.side === 'BUY' ? 'success' : 'destructive'}>{f.side}</Badge>
                        </td>
                        <td className="px-4 py-3 text-right font-mono">{f.quantity}</td>
                        <td className="px-4 py-3 text-right font-mono">{formatCurrency(f.price, 'INR')}</td>
                        <td className="px-6 py-3 text-right font-mono text-muted-foreground">
                          {formatCurrency(f.costs, 'INR')}
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
            {sorted.length > visible && (
              <div className="p-4 flex justify-center border-t border-border/50">
                <Button variant="ghost" size="sm" onClick={() => setVisible((v) => v + PAGE_SIZE)}>
                  Show more
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default FillsTable;
