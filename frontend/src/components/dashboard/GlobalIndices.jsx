import React from 'react';
import { Card, CardContent } from '../common/Card';
import { ArrowUp, ArrowDown, Globe } from 'lucide-react';
import { cn } from '../../utils/cn';

const GlobalIndices = ({ indices, isLoading, onIndexClick }) => {
    if (isLoading) {
        return (
            <div className="space-y-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    <Globe className="w-5 h-5 text-primary" /> Global Markets
                </h3>
                <div className="space-y-3">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-16 bg-muted/20 animate-pulse rounded-lg" />
                    ))}
                </div>
            </div>
        );
    }

    if (!indices || indices.length === 0) return null;

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
                <Globe className="w-5 h-5 text-primary" /> Global Markets
            </h3>
            <div className="grid grid-cols-1 gap-3">
                {indices.map((idx) => (
                    <Card 
                        key={idx.name} 
                        className="hover:border-primary/30 transition-colors cursor-pointer hover:bg-muted/5"
                        onClick={() => onIndexClick && onIndexClick(idx.symbol)}
                    >
                        <CardContent className="p-3 flex items-center justify-between">
                            <div>
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{idx.name}</p>
                                <p className="text-base font-bold font-mono">{idx.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                            </div>
                            <div className={cn(
                                "flex items-center gap-1 text-sm font-medium",
                                idx.change >= 0 ? "text-emerald-400" : "text-rose-400"
                            )}>
                                {idx.change >= 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                                {Math.abs(idx.percent).toFixed(2)}%
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};

export default GlobalIndices;
