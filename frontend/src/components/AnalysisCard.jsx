import React from 'react';
import { 
  TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle, 
  Newspaper, BarChart3, Target, DollarSign, Activity, 
  ArrowUp, ArrowDown, ExternalLink, Building2, ChevronRight,
  Sparkles, Zap, Shield
} from 'lucide-react';
import { clsx } from 'clsx';
import { 
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  ReferenceLine, CartesianGrid 
} from 'recharts';

const AnalysisCard = ({ data }) => {
  if (!data) return null;

  const { 
    decision, 
    reasoning, 
    analyst_summary, 
    quant_signals_count, 
    final_signal,
    company_info,
    sentiment_score,
    impact_score,
    news_articles,
    events,
    technical_analysis,
    all_signals,
    price_data,
    agent_confidence
  } = data;

  const getDecisionStyles = (d) => {
    switch (d?.toUpperCase()) {
      case 'BUY': return {
        bg: 'from-emerald-500/20 via-green-500/20 to-teal-500/20',
        border: 'border-emerald-500/40',
        text: 'text-emerald-400',
        glow: 'shadow-emerald-500/20'
      };
      case 'SELL': return {
        bg: 'from-red-500/20 via-rose-500/20 to-pink-500/20',
        border: 'border-red-500/40',
        text: 'text-red-400',
        glow: 'shadow-red-500/20'
      };
      default: return {
        bg: 'from-amber-500/20 via-yellow-500/20 to-orange-500/20',
        border: 'border-amber-500/40',
        text: 'text-amber-400',
        glow: 'shadow-amber-500/20'
      };
    }
  };

  const getIcon = (d) => {
    switch (d?.toUpperCase()) {
      case 'BUY': return <TrendingUp className="w-10 h-10" />;
      case 'SELL': return <TrendingDown className="w-10 h-10" />;
      default: return <Minus className="w-10 h-10" />;
    }
  };

  const formatCurrency = (value) => {
    if (!value && value !== 0) return '---';
    return new Intl.NumberFormat('en-US', { 
      style: 'currency', 
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2 
    }).format(value);
  };

  const formatLargeNumber = (value) => {
    if (!value) return '---';
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    return `$${value.toLocaleString()}`;
  };

  const formatChartData = () => {
    if (!price_data || price_data.length === 0) return [];
    return price_data.map((candle) => ({
      date: new Date(candle.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      price: candle.close,
      high: candle.high,
      low: candle.low,
      volume: candle.volume
    }));
  };

  const getSentimentColor = (score) => {
    if (score >= 0.3) return 'text-emerald-400';
    if (score <= -0.3) return 'text-red-400';
    return 'text-amber-400';
  };

  const getSentimentLabel = (score) => {
    if (score >= 0.5) return 'Very Bullish';
    if (score >= 0.2) return 'Bullish';
    if (score <= -0.5) return 'Very Bearish';
    if (score <= -0.2) return 'Bearish';
    return 'Neutral';
  };

  const chartData = formatChartData();
  const currentPrice = company_info?.current_price || (chartData.length > 0 ? chartData[chartData.length - 1]?.price : 0);
  const isPositiveChange = (company_info?.day_change_percent || 0) >= 0;
  const decisionStyles = getDecisionStyles(decision);

  return (
    <div className="space-y-6">
      
      {/* Stock Header with Company Info */}
      {company_info && (
        <div className="p-6 rounded-2xl glass border border-white/10 card-hover">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div className="flex items-center gap-5">
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl blur opacity-40 group-hover:opacity-60 transition-opacity duration-300" />
                <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-xl">
                  <Building2 className="w-8 h-8 text-white" />
                </div>
              </div>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-3xl font-bold text-white">{company_info.symbol}</h1>
                  {company_info.sector && (
                    <span className="px-3 py-1 text-xs font-medium rounded-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 text-blue-300 border border-blue-500/30">
                      {company_info.sector}
                    </span>
                  )}
                </div>
                <p className="text-slate-400 text-lg">{company_info.name}</p>
              </div>
            </div>
            
            <div className="text-right lg:text-right">
              <div className="text-4xl font-bold text-white mb-1">{formatCurrency(currentPrice)}</div>
              <div className={clsx(
                "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold",
                isPositiveChange 
                  ? "bg-emerald-500/20 text-emerald-400" 
                  : "bg-red-500/20 text-red-400"
              )}>
                {isPositiveChange ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
                <span>{formatCurrency(Math.abs(company_info.day_change || 0))}</span>
                <span>({(company_info.day_change_percent || 0).toFixed(2)}%)</span>
              </div>
            </div>
          </div>
          
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-white/10">
            <MetricItem label="Market Cap" value={formatLargeNumber(company_info.market_cap)} />
            <MetricItem label="Volume" value={company_info.volume ? (company_info.volume / 1e6).toFixed(2) + 'M' : '---'} />
            <MetricItem label="52W High" value={formatCurrency(company_info.week_52_high)} color="text-emerald-400" />
            <MetricItem label="52W Low" value={formatCurrency(company_info.week_52_low)} color="text-red-400" />
          </div>
        </div>
      )}

      {/* Price Chart */}
      {chartData.length > 0 && (
        <div className="p-6 rounded-2xl glass border border-white/10 card-hover">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h3 className="font-semibold text-white">Price Chart</h3>
                <p className="text-xs text-slate-500">Last 60 days</p>
              </div>
            </div>
            {technical_analysis && (
              <div className={clsx(
                "px-4 py-2 rounded-xl text-sm font-semibold border",
                technical_analysis.trend === 'up' ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
                technical_analysis.trend === 'down' ? "bg-red-500/10 text-red-400 border-red-500/30" :
                "bg-amber-500/10 text-amber-400 border-amber-500/30"
              )}>
                Trend: {technical_analysis.trend?.toUpperCase() || 'UNKNOWN'}
              </div>
            )}
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis 
                  dataKey="date" 
                  stroke="#64748b" 
                  tick={{ fill: '#64748b', fontSize: 11 }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                />
                <YAxis 
                  stroke="#64748b" 
                  tick={{ fill: '#64748b', fontSize: 11 }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  domain={['auto', 'auto']}
                  tickFormatter={(value) => `$${value.toFixed(0)}`}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'rgba(15, 23, 42, 0.95)', 
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    padding: '12px',
                    backdropFilter: 'blur(10px)'
                  }}
                  labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                  formatter={(value) => [`$${value.toFixed(2)}`, 'Price']}
                />
                {technical_analysis?.nearest_support > 0 && (
                  <ReferenceLine 
                    y={technical_analysis.nearest_support} 
                    stroke="#22c55e" 
                    strokeDasharray="8 4" 
                    strokeWidth={2}
                    label={{ value: `Support: $${technical_analysis.nearest_support.toFixed(2)}`, fill: '#22c55e', fontSize: 11, position: 'right' }}
                  />
                )}
                {technical_analysis?.nearest_resistance > 0 && (
                  <ReferenceLine 
                    y={technical_analysis.nearest_resistance} 
                    stroke="#ef4444" 
                    strokeDasharray="8 4"
                    strokeWidth={2}
                    label={{ value: `Resistance: $${technical_analysis.nearest_resistance.toFixed(2)}`, fill: '#ef4444', fontSize: 11, position: 'right' }}
                  />
                )}
                <Area 
                  type="monotone" 
                  dataKey="price" 
                  stroke="#8b5cf6" 
                  strokeWidth={2.5}
                  fillOpacity={1} 
                  fill="url(#priceGradient)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* AI Decision Card */}
      <div className={clsx(
        "relative p-8 rounded-2xl bg-gradient-to-br border backdrop-blur-xl shadow-2xl overflow-hidden",
        decisionStyles.bg, decisionStyles.border, decisionStyles.glow
      )}>
        {/* Background glow */}
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent" />
        
        <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div className="flex items-center gap-5">
            <div className={clsx("p-4 rounded-2xl bg-white/10 backdrop-blur-sm", decisionStyles.text)}>
              {getIcon(decision)}
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <span className="text-sm text-slate-400 uppercase tracking-wider font-medium">AI Decision</span>
              </div>
              <span className={clsx("text-5xl font-bold", decisionStyles.text)}>
                {decision?.toUpperCase()}
              </span>
            </div>
          </div>
          
          <div className="text-center md:text-right">
            <div className="text-sm text-slate-400 mb-2">Confidence Score</div>
            <div className={clsx("text-4xl font-bold", decisionStyles.text)}>
              {((agent_confidence || 0.5) * 100).toFixed(0)}%
            </div>
            <div className="w-32 h-2 bg-white/10 rounded-full mt-3 overflow-hidden mx-auto md:ml-auto md:mr-0">
              <div 
                className={clsx("h-full rounded-full transition-all duration-1000", 
                  decision?.toUpperCase() === 'BUY' ? 'bg-gradient-to-r from-emerald-500 to-teal-400' :
                  decision?.toUpperCase() === 'SELL' ? 'bg-gradient-to-r from-red-500 to-rose-400' :
                  'bg-gradient-to-r from-amber-500 to-yellow-400'
                )}
                style={{ width: `${(agent_confidence || 0.5) * 100}%` }}
              />
            </div>
          </div>
        </div>
        
        <div className="relative mt-6 pt-6 border-t border-white/10">
          <p className="text-lg text-slate-300 leading-relaxed">{reasoning}</p>
        </div>
      </div>

      {/* Analysis Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Sentiment Card */}
        <div className="p-6 rounded-2xl glass border border-white/10 card-hover">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
              <Activity className="w-5 h-5 text-cyan-400" />
            </div>
            <h3 className="font-semibold text-white">Sentiment</h3>
          </div>
          
          <div className="text-center mb-6">
            <div className={clsx("text-5xl font-bold mb-2", getSentimentColor(sentiment_score || 0))}>
              {((sentiment_score || 0) * 100).toFixed(0)}
            </div>
            <div className="text-sm text-slate-400">{getSentimentLabel(sentiment_score || 0)}</div>
          </div>
          
          <div className="relative h-3 rounded-full bg-gradient-to-r from-red-500 via-amber-500 to-emerald-500 overflow-visible">
            <div 
              className="absolute w-5 h-5 bg-white rounded-full shadow-lg -top-1 transform -translate-x-1/2 border-2 border-slate-800 transition-all duration-700"
              style={{ left: `${((sentiment_score || 0) + 1) * 50}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-slate-500 mt-2">
            <span>Bearish</span>
            <span>Neutral</span>
            <span>Bullish</span>
          </div>
        </div>

        {/* Technical Signals Card */}
        <div className="p-6 rounded-2xl glass border border-white/10 card-hover">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
              <Target className="w-5 h-5 text-purple-400" />
            </div>
            <h3 className="font-semibold text-white">Technical</h3>
          </div>
          
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 rounded-xl bg-white/5">
              <span className="text-slate-400">Active Signals</span>
              <span className="text-2xl font-bold text-white">{quant_signals_count}</span>
            </div>
            {technical_analysis && (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Support</span>
                  <span className="text-emerald-400 font-mono font-medium">{formatCurrency(technical_analysis.nearest_support)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Resistance</span>
                  <span className="text-red-400 font-mono font-medium">{formatCurrency(technical_analysis.nearest_resistance)}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Trade Setup Card */}
        <div className="p-6 rounded-2xl glass border border-white/10 card-hover">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500/20 to-red-500/20 flex items-center justify-center">
              <Shield className="w-5 h-5 text-orange-400" />
            </div>
            <h3 className="font-semibold text-white">Trade Setup</h3>
          </div>
          
          <div className="space-y-3">
            <div className="flex justify-between items-center p-2 rounded-lg bg-white/5">
              <span className="text-sm text-slate-400">Entry</span>
              <span className="font-mono font-medium text-white">{formatCurrency(final_signal?.entry_price)}</span>
            </div>
            <div className="flex justify-between items-center p-2 rounded-lg bg-red-500/5">
              <span className="text-sm text-slate-400">Stop Loss</span>
              <span className="font-mono font-medium text-red-400">{formatCurrency(final_signal?.stop_loss)}</span>
            </div>
            <div className="flex justify-between items-center p-2 rounded-lg bg-emerald-500/5">
              <span className="text-sm text-slate-400">Target</span>
              <span className="font-mono font-medium text-emerald-400">{formatCurrency(final_signal?.target_price)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Analyst Summary */}
      <div className="p-6 rounded-2xl glass border border-white/10 card-hover">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center">
            <CheckCircle className="w-5 h-5 text-blue-400" />
          </div>
          <h3 className="font-semibold text-white">Market Analysis Summary</h3>
        </div>
        <p className="text-slate-300 leading-relaxed">
          {analyst_summary || "No analysis summary available."}
        </p>
      </div>

      {/* News Articles */}
      {news_articles && news_articles.length > 0 && (
        <div className="p-6 rounded-2xl glass border border-white/10">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center">
              <Newspaper className="w-5 h-5 text-emerald-400" />
            </div>
            <h3 className="font-semibold text-white">Latest News</h3>
          </div>
          <div className="space-y-3">
            {news_articles.slice(0, 5).map((article, idx) => (
              <a 
                key={idx}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 transition-all duration-200 group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-white group-hover:text-blue-400 transition-colors line-clamp-2 mb-2">
                      {article.title}
                    </h4>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                      <span className="font-medium">{article.source}</span>
                      <span>•</span>
                      <span>{new Date(article.published_at).toLocaleDateString()}</span>
                      {article.sentiment && (
                        <span className={clsx(
                          "px-2 py-0.5 rounded-full font-medium",
                          article.sentiment === 'positive' ? "bg-emerald-500/20 text-emerald-400" :
                          article.sentiment === 'negative' ? "bg-red-500/20 text-red-400" :
                          "bg-amber-500/20 text-amber-400"
                        )}>
                          {article.sentiment}
                        </span>
                      )}
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-slate-500 group-hover:text-blue-400 transition-colors flex-shrink-0 mt-1" />
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const MetricItem = ({ label, value, color = "text-white" }) => (
  <div className="text-center md:text-left">
    <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</div>
    <div className={clsx("text-lg font-semibold", color)}>{value}</div>
  </div>
);

export default AnalysisCard;
