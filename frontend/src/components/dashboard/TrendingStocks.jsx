import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { ArrowUp, ArrowRight, TrendingUp } from 'lucide-react';

const TrendingStocks = () => {
    const trending = [
        { symbol: 'RELIANCE', name: 'Reliance Industries', price: 2450.50, change: 1.2 },
        { symbol: 'TCS', name: 'Tata Consultancy Svc', price: 3450.10, change: 0.8 },
        { symbol: 'HDFCBANK', name: 'HDFC Bank', price: 1650.00, change: 1.5 },
        { symbol: 'INFY', name: 'Infosys Ltd', price: 1420.30, change: -0.5 }, // Mixed
        { symbol: 'ADANIENT', name: 'Adani Enterprises', price: 3100.00, change: 2.1 },
    ];

    return (
        <Card className="h-full">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <TrendingUp className="w-4 h-4 text-blue-400" />
                    Trending Tickers
                </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="divide-y divide-border/50">
                    {trending.map((stock) => (
                        <div key={stock.symbol} className="flex items-center justify-between p-4 hover:bg-muted/30 transition-colors cursor-pointer group">
                            <div>
                                <div className="font-bold text-sm group-hover:text-blue-400 transition-colors">{stock.symbol}</div>
                                <div className="text-xs text-muted-foreground">{stock.name}</div>
                            </div>
                            <div className="text-right">
                                <div className="font-mono text-sm font-medium">₹{stock.price.toLocaleString()}</div>
                                <div className={`text-xs flex items-center justify-end gap-1 ${stock.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {stock.change >= 0 ? '+' : ''}{stock.change}%
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="p-3 border-t border-border/50 text-center">
                    <button className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center justify-center gap-1 w-full">
                        View All Market Movers <ArrowRight className="w-3 h-3" />
                    </button>
                </div>
            </CardContent>
        </Card>
    );
};

export default TrendingStocks;
