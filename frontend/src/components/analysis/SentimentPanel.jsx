import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Gauge, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '../../utils/cn';

const SentimentPanel = ({ score, summary }) => {
    // Score -1 to 1
    const getSentimentConfig = (s) => {
        if (s >= 0.3) return { label: 'Bullish', color: 'text-emerald-400', bg: 'bg-emerald-500/20', icon: TrendingUp };
        if (s <= -0.3) return { label: 'Bearish', color: 'text-rose-400', bg: 'bg-rose-500/20', icon: TrendingDown };
        return { label: 'Neutral', color: 'text-amber-400', bg: 'bg-amber-500/20', icon: Minus };
    };

    const config = getSentimentConfig(score);
    const percentage = Math.round(((score + 1) / 2) * 100); // Map -1..1 to 0..100

    return (
        <Card className="h-full">
            <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <Gauge className="w-4 h-4 text-purple-400" />
                    Market Sentiment
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                <div className="flex items-center justify-center py-4">
                     <div className="relative w-40 h-20 overflow-hidden">
                        {/* Gauge Arc */}
                        <div className="absolute top-0 left-0 w-full h-full bg-muted rounded-t-full" />
                        <div 
                            className="absolute top-0 left-0 w-full h-full bg-gradient-to-r from-rose-500 via-amber-500 to-emerald-500 rounded-t-full origin-bottom transition-transform duration-1000 ease-out"
                            style={{ transform: `rotate(${percentage * 1.8 - 180}deg)` }}
                        />
                        {/* Cover inner part */}
                        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-28 h-14 bg-card rounded-t-full flex items-end justify-center pb-2">
                             <div className={cn("text-xl font-bold", config.color)}>
                                {config.label}
                             </div>
                        </div>
                     </div>
                </div>
                
                <div className="text-sm text-muted-foreground leading-relaxed border-t border-border/50 pt-4">
                    {summary}
                </div>
            </CardContent>
        </Card>
    );
};

export default SentimentPanel;
