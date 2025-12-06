import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { ShieldAlert, CheckCircle2, ShieldCheck } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

const RiskPanel = ({ signal }) => {
    // signal = { entry, stop_loss, target, risk_reward_ratio }
    if (!signal) return null;

    const rrr = signal.target_price && signal.stop_loss 
        ? ((signal.target_price - signal.entry_price) / (signal.entry_price - signal.stop_loss)).toFixed(2)
        : '---';

    return (
        <Card className="h-full border-l-4 border-l-purple-500/50">
            <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-purple-400" />
                    Risk Management
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-3 gap-2 text-center mb-6">
                    <div className="p-3 bg-muted/30 rounded-lg">
                         <div className="text-xs text-muted-foreground uppercase mb-1">Entry</div>
                         <div className="font-mono font-bold text-foreground">{formatCurrency(signal.entry_price)}</div>
                    </div>
                    <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg">
                         <div className="text-xs text-rose-400 uppercase mb-1">Stop</div>
                         <div className="font-mono font-bold text-rose-400">{formatCurrency(signal.stop_loss)}</div>
                    </div>
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                         <div className="text-xs text-emerald-400 uppercase mb-1">Target</div>
                         <div className="font-mono font-bold text-emerald-400">{formatCurrency(signal.target_price)}</div>
                    </div>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                    <span className="text-sm font-medium text-muted-foreground">Risk/Reward Ratio</span>
                    <span className="font-mono font-bold text-foreground">1 : {rrr}</span>
                </div>
            </CardContent>
        </Card>
    );
};

export default RiskPanel;
