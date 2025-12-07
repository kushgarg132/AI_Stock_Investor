import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { ShieldAlert, CheckCircle2, ShieldCheck } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { cn } from '../../utils/cn';

const RiskPanel = ({ signal, risk, currency }) => {
    // signal = { entry, stop_loss, target, risk_reward_ratio }
    const rrr = signal?.target_price && signal?.stop_loss && signal?.entry_price
        ? Math.abs((signal.target_price - signal.entry_price) / (signal.entry_price - signal.stop_loss)).toFixed(2)
        : '---';

    const getRiskColor = (level) => {
        if (!level) return 'text-muted-foreground';
        const l = level.toLowerCase();
        if (l === 'low') return 'text-emerald-400';
        if (l === 'medium') return 'text-amber-400';
        return 'text-rose-400';
    }

    return (
        <Card className="h-full border-l-4 border-l-purple-500/50">
            <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-purple-400" />
                    Risk Management
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-2 gap-4 mb-4">
                     <div className="p-3 bg-muted/30 rounded-lg text-center">
                        <div className="text-xs text-muted-foreground uppercase mb-1">Risk Level</div>
                        <div className={cn("font-bold text-lg", getRiskColor(risk?.risk_level))}>
                            {risk?.risk_level || '---'}
                        </div>
                     </div>
                     <div className="p-3 bg-muted/30 rounded-lg text-center">
                        <div className="text-xs text-muted-foreground uppercase mb-1">Volatility</div>
                        <div className="font-mono font-bold text-lg">
                            {risk?.volatility_score ? (risk.volatility_score * 100).toFixed(1) + '%' : '---'}
                        </div>
                     </div>
                </div>

                {signal && (
                    <div className="grid grid-cols-3 gap-2 text-center mb-6">
                        <div className="p-2 bg-muted/30 rounded-lg">
                             <div className="text-xs text-muted-foreground uppercase mb-1">Entry</div>
                             <div className="font-mono font-bold text-sm">{formatCurrency(signal.entry_price, currency)}</div>
                        </div>
                        <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded-lg">
                             <div className="text-xs text-rose-400 uppercase mb-1">Stop</div>
                             <div className="font-mono font-bold text-sm text-rose-400">{formatCurrency(signal.stop_loss, currency)}</div>
                        </div>
                        <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                             <div className="text-xs text-emerald-400 uppercase mb-1">Target</div>
                             <div className="font-mono font-bold text-sm text-emerald-400">{formatCurrency(signal.target_price, currency)}</div>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                    <span className="text-sm font-medium text-muted-foreground">Risk/Reward Ratio</span>
                    <span className="font-mono font-bold text-foreground">1 : {rrr}</span>
                </div>
            </CardContent>
        </Card>
    );
};

export default RiskPanel;
