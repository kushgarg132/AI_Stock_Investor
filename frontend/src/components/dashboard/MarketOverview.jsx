import React from 'react';
import { Card, CardContent } from '../common/Card';
import { ArrowUp, ArrowDown, Activity } from 'lucide-react';
import { cn } from '../../utils/cn';

const MarketOverview = ({ indices, isLoading }) => {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                {[1, 2, 3, 4].map(i => (
                    <Card key={i} className="h-24 bg-muted/20 animate-pulse border-border/50">
                        <CardContent className="p-4" />
                    </Card>
                ))}
            </div>
        );
    }

    if (!indices || indices.length === 0) return null;

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {indices.map((idx) => (
                <Card key={idx.name} className="hover:border-primary/30 transition-colors">
                    <CardContent className="p-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">{idx.name}</p>
                            <p className="text-lg font-bold font-mono">{idx.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                        </div>
                        <div className={cn(
                            "flex flex-col items-end text-sm font-medium",
                            idx.change >= 0 ? "text-emerald-400" : "text-rose-400"
                        )}>
                            <span className="flex items-center gap-1">
                                {idx.change >= 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                                {Math.abs(idx.percent).toFixed(2)}%
                            </span>
                            <span className="text-xs opacity-80">{idx.change > 0 ? '+' : ''}{idx.change.toFixed(2)}</span>
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
};

export default MarketOverview;
