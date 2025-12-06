import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { ScanLine, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import { formatCurrency } from '../utils/formatters';

const ScannerPage = () => {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const runScanner = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post('http://localhost:8001/api/v1/agents/scanner/bullish');
      setResults(response.data.results);
    } catch (err) {
      console.error(err);
      setError("Failed to run scanner. Backend might be unreachable.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = (symbol) => {
    navigate('/', { state: { symbol } });
  };

  return (
    <Layout>
      <div className="space-y-8 animate-in fade-in duration-500">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
                <h1 className="text-3xl font-bold tracking-tight mb-2">Market Scanner</h1>
                <p className="text-muted-foreground">Find high-potential opportunities driven by AI analysis.</p>
            </div>
            
            <Button 
                onClick={runScanner} 
                disabled={loading} 
                size="lg" 
                className="w-full md:w-auto shadow-blue-500/20 shadow-lg"
            >
                {loading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <ScanLine className="w-5 h-5 mr-2" />}
                {loading ? 'Scanning Markets...' : 'Run Bullish Scan'}
            </Button>
        </div>

        {/* Error State */}
        {error && (
            <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive flex items-center gap-3">
                <AlertCircle className="w-5 h-5" />
                <span>{error}</span>
            </div>
        )}

        {/* Empty State */}
        {!results && !loading && !error && (
            <div className="h-64 flex flex-col items-center justify-center text-center p-8 rounded-2xl border-2 border-dashed border-border/50 bg-muted/10">
                <div className="w-16 h-16 rounded-full bg-muted/30 flex items-center justify-center mb-4">
                    <ScanLine className="w-8 h-8 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-semibold mb-1">Ready to Scan</h3>
                <p className="text-sm text-muted-foreground max-w-sm">
                    Click "Run Bullish Scan" to have our Quant Agent analyze the Nifty Smallcap 100 for breakout candidates.
                </p>
            </div>
        )}

        {/* Results Grid */}
        {results && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {results.map((stock, idx) => (
                    <Card key={idx} className="group hover:border-primary/50 transition-all duration-300">
                        <CardContent className="p-6">
                            <div className="flex justify-between items-start mb-4">
                                <div>
                                    <h3 className="text-xl font-bold group-hover:text-primary transition-colors">{stock.symbol}</h3>
                                    <div className="flex items-center gap-2 mt-1">
                                        <Badge variant="success">Strong Buy</Badge>
                                        <span className="text-xs text-muted-foreground font-mono">Signal: {(stock.signal_strength * 100).toFixed(0)}%</span>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-sm text-muted-foreground">Target</div>
                                    <div className="font-mono font-bold text-emerald-400">{formatCurrency(stock.target_price)}</div>
                                </div>
                            </div>
                            
                            <div className="space-y-3 mb-6">
                                <div className="p-3 rounded-lg bg-muted/50 text-sm">
                                    <span className="text-muted-foreground">Stop Loss:</span>
                                    <span className="float-right font-mono font-medium text-rose-400">{formatCurrency(stock.stop_loss)}</span>
                                </div>
                                <div className="text-sm text-muted-foreground leading-relaxed line-clamp-2">
                                    {stock.reason}
                                </div>
                            </div>

                            <Button 
                                variant="outline" 
                                className="w-full group-hover:bg-primary group-hover:text-primary-foreground group-hover:border-primary transition-all"
                                onClick={() => handleAnalyze(stock.symbol)}
                            >
                                Deep Analysis <ArrowRight className="w-4 h-4 ml-2" />
                            </Button>
                        </CardContent>
                    </Card>
                ))}
            </div>
        )}
      </div>
    </Layout>
  );
};

export default ScannerPage;
