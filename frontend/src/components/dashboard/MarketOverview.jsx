import React from 'react';
import { Card, CardContent } from '../common/Card';
import { ArrowUp, ArrowDown, Activity } from 'lucide-react';
import { cn } from '../../utils/cn';

const MarketOverview = () => {
    // Mock Data for Indices (Replace with real API later)
    const indices = [
        { name: 'NIFTY 50', value: 24852.15, change: 125.40, percent: 0.52 },
        { name: 'SENSEX', value: 81234.50, change: -150.20, percent: -0.18 },
        { name: 'BANK NIFTY', value: 52400.10, change: 320.60, percent: 0.65 },
        { name: 'INDIA VIX', value: 12.45, change: -0.50, percent: -3.85 },
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {indices.map((idx) => (
                <Card key={idx.name} className="hover:border-primary/30 transition-colors">
                    <CardContent className="p-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">{idx.name}</p>
                            <p className="text-lg font-bold font-mono">{idx.value.toLocaleString()}</p>
                        </div>
                        <div className={cn(
                            "flex flex-col items-end text-sm font-medium",
                            idx.change >= 0 ? "text-emerald-400" : "text-rose-400"
                        )}>
                            <span className="flex items-center gap-1">
                                {idx.change >= 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                                {Math.abs(idx.percent)}%
                            </span>
                            <span className="text-xs opacity-80">{idx.change > 0 ? '+' : ''}{idx.change}</span>
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
};

export default MarketOverview;
