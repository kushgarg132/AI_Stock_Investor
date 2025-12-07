import React, { useState } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  CartesianGrid, Bar, ComposedChart, ReferenceLine 
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { formatCurrency, formatCompactNumber } from '../../utils/formatters';
import { Maximize2, BarChart2, TrendingUp } from 'lucide-react';
import { cn } from '../../utils/cn';

const TradingChart = ({ data, technicals, className, currency }) => {
  const [timeframe, setTimeframe] = useState('1Y');
  const [chartType, setChartType] = useState('area');
  
  // Filter data based on timeframe
  const filteredData = React.useMemo(() => {
    if (!data) return [];
    let days = 365;
    if (timeframe === '1M') days = 22;
    if (timeframe === '3M') days = 66;
    if (timeframe === '6M') days = 132;
    
    // Slice from the end
    return data.slice(-days);
  }, [data, timeframe]);

  // Format data for Recharts
  const formattedData = filteredData.map(item => ({
    ...item,
    date: new Date(item.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    price: Number(item.close),
    volume: Number(item.volume)
  }));

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const p = payload[0].payload;
      return (
        <div className="bg-popover/95 border border-border p-3 rounded-xl shadow-xl backdrop-blur-md">
           <p className="text-xs text-muted-foreground mb-1">{label}</p>
           <div className="space-y-0.5">
              <div className="flex items-center gap-4 justify-between">
                <span className="text-sm font-bold text-foreground">{formatCurrency(p.price, currency)}</span>
                <span className={cn(
                    "text-xs font-medium",
                    p.close >= p.open ? "text-emerald-400" : "text-rose-400"
                )}>
                    {((p.close - p.open) / p.open * 100).toFixed(2)}%
                </span>
              </div>
              <div className="flex items-center gap-4 justify-between text-xs text-muted-foreground">
                 <span>Vol:</span>
                 <span className="font-mono">{formatCompactNumber(p.volume)}</span>
              </div>
           </div>
        </div>
      );
    }
    return null;
  };

  return (
    <Card className={cn("flex flex-col h-[500px]", className)}>
        <CardHeader className="flex flex-row items-center justify-between py-4 border-b border-border/50">
            <div className="flex items-center gap-4">
                <CardTitle className="flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-primary" />
                    Price Action
                </CardTitle>
                <div className="flex bg-muted/50 rounded-lg p-1">
                    {['1M', '3M', '6M', '1Y'].map(tf => (
                         <button
                            key={tf}
                            onClick={() => setTimeframe(tf)}
                            className={cn(
                                "px-3 py-1 text-xs font-medium rounded-md transition-all",
                                timeframe === tf ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            {tf}
                        </button>
                    ))}
                </div>
            </div>
            
            <div className="flex items-center gap-2">
                 <Button variant="ghost" size="sm" onClick={() => setChartType(chartType === 'area' ? 'bar' : 'area')}>
                    <TrendingUp className="w-4 h-4" />
                 </Button>
                 <Button variant="ghost" size="sm">
                    <Maximize2 className="w-4 h-4" />
                 </Button>
            </div>
        </CardHeader>

        <CardContent className="flex-1 p-0 relative">
            {formattedData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={formattedData} margin={{ top: 20, right: 0, left: 0, bottom: 0 }}>
                        <defs>
                            <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                        <XAxis 
                            dataKey="date" 
                            stroke="#64748b"
                            tick={{ fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            minTickGap={30}
                        />
                        <YAxis 
                            yAxisId="right"
                            orientation="right"
                            domain={['auto', 'auto']}
                            stroke="#64748b"
                            tick={{ fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(val) => {
                                const locale = (currency === 'INR') ? 'en-IN' : 'en-US';
                                return new Intl.NumberFormat(locale, { style: 'currency', currency: currency || 'USD', maximumFractionDigits: 0 }).format(val);
                            }}
                            width={80}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }} />
                        
                        {technicals?.nearest_support && (
                             <ReferenceLine yAxisId="right" y={technicals.nearest_support} stroke="#22c55e" strokeDasharray="5 5" label={{ value: 'SUP', fill: '#22c55e', fontSize: 10, position: 'insideLeft' }} />
                        )}
                        {technicals?.nearest_resistance && (
                             <ReferenceLine yAxisId="right" y={technicals.nearest_resistance} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'RES', fill: '#ef4444', fontSize: 10, position: 'insideLeft' }} />
                        )}

                        <Area 
                            yAxisId="right"
                            type="monotone" 
                            dataKey="price" 
                            stroke="#3b82f6" 
                            strokeWidth={2}
                            fillOpacity={1} 
                            fill="url(#colorPrice)" 
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            ) : (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                    No Data Available
                </div>
            )}
        </CardContent>
    </Card>
  );
};

export default TradingChart;
