import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Activity, ArrowRight } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

const TechnicalPanel = ({ signals }) => {
    // signals = array of { signal, action, confidence }
    if (!signals || signals.length === 0) return null;

    return (
        <Card className="h-full">
            <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary" />
                    Technical Signals
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-3">
                    {signals.slice(0, 4).map((sig, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors">
                            <span className="text-sm font-medium">{sig.signal || sig.indicator}</span>
                            <div className="flex items-center gap-3">
                                <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                                    sig.action === 'buy' ? 'bg-emerald-500/10 text-emerald-400' : 
                                    sig.action === 'sell' ? 'bg-rose-500/10 text-rose-400' : 
                                    'bg-amber-500/10 text-amber-400'
                                }`}>
                                    {sig.action}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

export default TechnicalPanel;
