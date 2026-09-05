import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '../common/Card';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { Badge } from '../common/Badge';
import { Search, X, ChevronDown, Play, Square } from 'lucide-react';
import api, { endpoints } from '../../utils/api';
import { cn } from '../../utils/cn';

const MODES = ['LONGTERM', 'INTRADAY'];

const TradingControlBar = ({
  mode,
  onModeChange,
  universeSymbols,
  onUniverseChange,
  accountSize,
  onAccountSizeChange,
  maxExposure,
  onMaxExposureChange,
  isActive,
  onStart,
  onStop,
  busy,
  startError,
}) => {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState([]);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    if (!query.trim()) return undefined;
    const handle = setTimeout(async () => {
      try {
        const res = await api.get(endpoints.trading.instruments(query.trim()));
        setMatches(res.data);
      } catch {
        setMatches([]);
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [query]);

  const visibleMatches = query.trim() ? matches : [];

  const addSymbol = (symbol) => {
    if (!universeSymbols.includes(symbol)) {
      onUniverseChange([...universeSymbols, symbol]);
    }
    setQuery('');
    setMatches([]);
  };

  const removeSymbol = (symbol) => {
    onUniverseChange(universeSymbols.filter((s) => s !== symbol));
  };

  return (
    <Card className="glass">
      <CardContent className="p-6 space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-start gap-6">
          {/* Mode toggle */}
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Mode</p>
            <div className="flex bg-muted/50 rounded-lg p-1">
              {MODES.map((m) => (
                <button
                  key={m}
                  disabled={isActive}
                  onClick={() => onModeChange(m)}
                  className={cn(
                    'px-4 py-1.5 text-xs font-medium rounded-md transition-all disabled:cursor-not-allowed disabled:opacity-60',
                    mode === m ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {/* Universe picker */}
          <div className="flex-1 relative">
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
              Universe {universeSymbols.length === 0 && <span className="normal-case">(default, 83 symbols)</span>}
            </p>
            {!isActive && (
              <Input
                icon={<Search className="w-4 h-4" />}
                placeholder="Search symbol to add (e.g. RELIANCE)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            )}
            {visibleMatches.length > 0 && (
              <div className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto rounded-lg border border-border bg-popover shadow-xl custom-scrollbar">
                {visibleMatches.map((m) => (
                  <button
                    key={m.tradingsymbol}
                    onClick={() => addSymbol(m.tradingsymbol)}
                    className="w-full flex items-center justify-between px-3 py-2 text-sm text-left hover:bg-muted/50"
                  >
                    <span className="font-mono">{m.tradingsymbol}</span>
                    <span className="text-muted-foreground text-xs truncate ml-2">{m.name}</span>
                  </button>
                ))}
              </div>
            )}
            {universeSymbols.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {universeSymbols.map((s) => (
                  <Badge key={s} variant="secondary" className="gap-1.5 pr-1.5">
                    <span className="font-mono">{s}</span>
                    {!isActive && (
                      <button onClick={() => removeSymbol(s)} className="hover:text-foreground">
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Start/Stop */}
          <div className="flex items-end">
            {isActive ? (
              <Button variant="danger" onClick={onStop} disabled={busy}>
                <Square className="w-4 h-4 mr-2" /> Stop Run
              </Button>
            ) : (
              <Button variant="primary" onClick={onStart} disabled={busy}>
                <Play className="w-4 h-4 mr-2" /> Start Run
              </Button>
            )}
          </div>
        </div>

        {startError && (
          <p className="text-sm text-destructive">{startError}</p>
        )}

        {/* Advanced disclosure */}
        <div>
          <button
            onClick={() => setAdvancedOpen((v) => !v)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', advancedOpen && 'rotate-180')} />
            Advanced
          </button>
          {advancedOpen && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3 max-w-md">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Account Size</p>
                <Input
                  type="number"
                  disabled={isActive}
                  value={accountSize}
                  onChange={(e) => onAccountSizeChange(Number(e.target.value))}
                />
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Max Exposure</p>
                <Input
                  type="number"
                  disabled={isActive}
                  value={maxExposure}
                  onChange={(e) => onMaxExposureChange(Number(e.target.value))}
                />
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default TradingControlBar;
