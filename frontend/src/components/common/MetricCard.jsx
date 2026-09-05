import React from 'react';
import { HelpCircle } from 'lucide-react';
import { Card, CardContent } from './Card';
import { cn } from '../../utils/cn';

const MetricCard = ({ label, value, highlight, hint, className }) => (
  <Card className={cn('hover:border-primary/20 transition-colors', className)}>
    <CardContent className="p-4">
      <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-1">
        {label}
        {hint && <HelpCircle className="w-3 h-3 shrink-0" title={hint} />}
      </p>
      <p className={cn(
        'text-lg font-bold font-mono',
        highlight === 'up' && 'text-up',
        highlight === 'down' && 'text-down'
      )}>{value}</p>
    </CardContent>
  </Card>
);

export { MetricCard };
