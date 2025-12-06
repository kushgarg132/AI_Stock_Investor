import React from 'react';
import { Building2, ArrowUp, ArrowDown, Globe } from 'lucide-react';
import { Card, CardContent } from './common/Card';
import { Badge } from './common/Badge';
import { formatCurrency, formatCompactNumber } from '../utils/formatters';
import { cn } from '../utils/cn';

// Panels
import TradingChart from './stock/TradingChart';
import SentimentPanel from './analysis/SentimentPanel';
import RiskPanel from './analysis/RiskPanel';
import TechnicalPanel from './analysis/TechnicalPanel';
import NewsFeed from './analysis/NewsFeed';
import EventsList from './analysis/EventsList';

const AnalysisCard = ({ data }) => {
  if (!data) return null;

  const { 
    company_info,
    price_data, 
    technical_analysis,
    sentiment_score,
    analyst_summary,
    final_signal,
    all_signals
  } = data;

  const isPositiveChange = (company_info?.day_change_percent || 0) >= 0;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* 1. Header Section */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 p-1">
        <div className="flex items-center gap-4">
             <div className="w-16 h-16 rounded-2xl bg-card border border-border flex items-center justify-center p-2 shadow-sm">
                 {company_info?.logo_url ? (
                     <img src={company_info.logo_url} alt={company_info.name} className="w-full h-full object-contain" />
                 ) : (
                     <Building2 className="w-8 h-8 text-muted-foreground" />
                 )}
             </div>
             <div>
                 <div className="flex items-center gap-3">
                     <h1 className="text-3xl font-bold tracking-tight">{company_info?.symbol}</h1>
                     <Badge variant="outline">{company_info?.sector}</Badge>
                 </div>
                 <p className="text-muted-foreground text-lg">{company_info?.name}</p>
             </div>
        </div>

        <div className="text-left md:text-right">
             <div className="text-4xl font-mono font-bold tracking-tight">{formatCurrency(company_info?.current_price)}</div>
             <div className={cn(
                 "flex items-center gap-2 text-lg font-medium justify-start md:justify-end",
                 isPositiveChange ? "text-emerald-400" : "text-rose-400"
             )}>
                 {isPositiveChange ? <ArrowUp className="w-5 h-5" /> : <ArrowDown className="w-5 h-5" />}
                 <span>{formatCurrency(Math.abs(company_info?.day_change))}</span>
                 <span>({(company_info?.day_change_percent || 0).toFixed(2)}%)</span>
             </div>
        </div>
      </div>

      {/* 2. Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
           {/* Chart Column (8 span) */}
           <div className="lg:col-span-8 flex flex-col gap-6">
                <TradingChart data={price_data} technicals={technical_analysis} />
                
                {/* Fundamentals Row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                     <MetricCard label="Market Cap" value={formatCompactNumber(company_info?.market_cap)} />
                     <MetricCard label="Volume" value={formatCompactNumber(company_info?.volume)} />
                     <MetricCard label="52W High" value={formatCurrency(company_info?.week_52_high)} highlight="up" />
                     <MetricCard label="52W Low" value={formatCurrency(company_info?.week_52_low)} highlight="down" />
                </div>
           </div>

           {/* Panels Column (4 span) */}
           <div className="lg:col-span-4 flex flex-col gap-6">
                <SentimentPanel score={sentiment_score} summary={analyst_summary} />
                <RiskPanel signal={final_signal} />
                <TechnicalPanel signals={all_signals} />
           </div>

           {/* 3. News & Events Row */}
           <div className="lg:col-span-8">
                <NewsFeed articles={data.news_articles} />
           </div>
           <div className="lg:col-span-4">
                <EventsList events={data.events} />
           </div>
      </div>
      
    </div>
  );
};

const MetricCard = ({ label, value, highlight }) => (
    <Card className="hover:border-primary/20 transition-colors">
        <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
            <p className={cn(
                "text-lg font-bold font-mono",
                highlight === 'up' && "text-emerald-400",
                highlight === 'down' && "text-rose-400"
            )}>{value}</p>
        </CardContent>
    </Card>
);

export default AnalysisCard;

