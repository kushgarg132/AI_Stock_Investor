import React from 'react';
import { cn } from '../../utils/cn';

const EmptyState = ({ icon: Icon, title, description, action, className }) => (
  <div className={cn(
    'flex flex-col items-center justify-center text-center p-8 rounded-2xl border-2 border-dashed border-border/50 bg-muted/10',
    className
  )}>
    {Icon && (
      <div className="w-16 h-16 rounded-full bg-muted/30 flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-muted-foreground" />
      </div>
    )}
    <h3 className="text-lg font-semibold mb-1">{title}</h3>
    {description && (
      <p className="text-sm text-muted-foreground max-w-sm">{description}</p>
    )}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export { EmptyState };
