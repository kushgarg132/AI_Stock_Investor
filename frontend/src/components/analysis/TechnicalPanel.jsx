import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Activity, ArrowRight } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { cn } from '../../utils/cn';

const TechnicalPanel = ({ signals, indicators, currency }) => {
    // signals = array of { signal, action, confidence }
    return (
        <Card className="h-full">
            <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary" />
                    Technical Analysis
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Indicators Grid */}
                    {indicators && (
                        <div className="grid grid-cols-2 gap-3 pb-4 border-b border-border/50">
                            <IndicatorItem 
                                label="RSI (14)" 
                                value={typeof indicators.rsi === 'number' ? indicators.rsi.toFixed(2) : '---'} 
                                status={!indicators.rsi ? 'Neutral' : indicators.rsi > 70 ? 'Overbought' : indicators.rsi < 30 ? 'Oversold' : 'Neutral'} 
                            />
                            <IndicatorItem 
                                label="MACD" 
                                value={typeof indicators.macd?.histogram === 'number' ? indicators.macd.histogram.toFixed(2) : '---'} 
                                status={!indicators.macd?.histogram ? 'Neutral' : indicators.macd.histogram > 0 ? 'Bullish' : 'Bearish'}
                            />
                            <IndicatorItem 
                                label="SMA 200" 
                                value={formatCurrency(indicators.sma_200, currency)} 
                                status="Trend"
                            />
                            <IndicatorItem 
                                label="ATR" 
                                value={typeof indicators.atr === 'number' ? indicators.atr.toFixed(2) : '---'} 
                                status="Vol"
                            />
                        </div>
                    )}

                    {/* Signals List */}
                    <div className="space-y-2">
                        {signals && signals.length > 0 ? signals.slice(0, 3).map((sig, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors">
                                <span className="text-xs font-medium truncate max-w-[120px]">{sig.signal || sig.indicator}</span>
                                <span className={cn(
                                    "text-xs font-bold uppercase px-2 py-0.5 rounded",
                                    sig.action === 'buy' ? 'bg-emerald-500/10 text-emerald-400' : 
                                    sig.action === 'sell' ? 'bg-rose-500/10 text-rose-400' : 
                                    'bg-amber-500/10 text-amber-400'
                                )}>
                                    {sig.action}
                                </span>
                            </div>
                        )) : (
                            <div className="text-center text-xs text-muted-foreground py-2">No active signals</div>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

const IndicatorItem = ({ label, value, status }) => (
    <div>
        <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-muted-foreground">{label}</span>
            <span className={cn(
                "text-[10px] uppercase font-bold px-1 rounded",
                status === 'Overbought' || status === 'Bearish' ? "text-rose-400 bg-rose-500/10" :
                status === 'Oversold' || status === 'Bullish' ? "text-emerald-400 bg-emerald-500/10" :
                "text-muted-foreground bg-muted"
            )}>{status}</span>
        </div>
        <div className="font-mono font-bold text-sm">{value || '---'}</div>
    </div>
);

export default TechnicalPanel;
