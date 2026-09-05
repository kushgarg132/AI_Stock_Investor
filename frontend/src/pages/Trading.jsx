import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import TradingControlBar from '../components/trading/TradingControlBar';
import RunStatusBanner from '../components/trading/RunStatusBanner';
import PositionsTable from '../components/trading/PositionsTable';
import FillsTable from '../components/trading/FillsTable';
import { MetricCard } from '../components/common/MetricCard';
import { useTradingPoll } from '../hooks/useTradingPoll';
import api, { endpoints } from '../utils/api';
import { formatCurrency } from '../utils/formatters';
import { AlertCircle } from 'lucide-react';

const STORAGE_RUN_ID = 'trading:runId';
const STORAGE_MODE = 'trading:mode';
const STORAGE_STARTED_AT = 'trading:startedAt';

const Trading = () => {
  const [runId, setRunId] = useState(() => localStorage.getItem(STORAGE_RUN_ID));
  const [mode, setMode] = useState(() => localStorage.getItem(STORAGE_MODE) || 'LONGTERM');
  const [startedAt, setStartedAt] = useState(() => localStorage.getItem(STORAGE_STARTED_AT));
  const [universeSymbols, setUniverseSymbols] = useState([]);
  const [accountSize, setAccountSize] = useState(1_000_000);
  const [maxExposure, setMaxExposure] = useState(1_000_000);
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState(null);
  const [ambiguous, setAmbiguous] = useState(false);

  const { positions, fills, equity } = useTradingPoll(!!runId);

  // One-time check at mount: if we have no run_id but the ledger already has
  // data, we can't tell whether a run is active elsewhere (no /trading/status
  // exists) -- surface that honestly rather than pretending we know.
  useEffect(() => {
    if (runId) return;
    (async () => {
      try {
        const res = await api.get(endpoints.trading.positions);
        if (Object.keys(res.data).length > 0) setAmbiguous(true);
      } catch {
        // ignore -- ambiguity check is best-effort
      }
    })();
  }, [runId]);

  const handleStart = async () => {
    setBusy(true);
    setStartError(null);
    try {
      const res = await api.post(endpoints.trading.start, {
        mode,
        universe: universeSymbols.length > 0 ? universeSymbols : undefined,
        account_size: accountSize,
        max_exposure: maxExposure,
      });
      const newRunId = res.data.run_id;
      const now = new Date().toISOString();
      localStorage.setItem(STORAGE_RUN_ID, newRunId);
      localStorage.setItem(STORAGE_MODE, mode);
      localStorage.setItem(STORAGE_STARTED_AT, now);
      setRunId(newRunId);
      setStartedAt(now);
      setAmbiguous(false);
    } catch (err) {
      setStartError(err.response?.data?.detail || 'Failed to start trading run.');
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    if (!runId) return;
    setBusy(true);
    setStartError(null);
    try {
      await api.post(endpoints.trading.stop, { run_id: runId });
    } catch (err) {
      // A 404 here means the run is already gone server-side -- still clear
      // our local state, there's nothing left to stop.
      if (err.response?.status !== 404) {
        setStartError(err.response?.data?.detail || 'Failed to stop trading run.');
        setBusy(false);
        return;
      }
    }
    localStorage.removeItem(STORAGE_RUN_ID);
    localStorage.removeItem(STORAGE_MODE);
    localStorage.removeItem(STORAGE_STARTED_AT);
    setRunId(null);
    setStartedAt(null);
    setBusy(false);
  };

  const positionCount = Object.keys(positions || {}).length;

  return (
    <Layout>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold">Trading</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Start or stop a paper-trading run and watch its positions and fills live.
          </p>
        </div>

        <TradingControlBar
          mode={mode}
          onModeChange={setMode}
          universeSymbols={universeSymbols}
          onUniverseChange={setUniverseSymbols}
          accountSize={accountSize}
          onAccountSizeChange={setAccountSize}
          maxExposure={maxExposure}
          onMaxExposureChange={setMaxExposure}
          isActive={!!runId}
          onStart={handleStart}
          onStop={handleStop}
          busy={busy}
          startError={startError}
        />

        <RunStatusBanner runId={runId} mode={mode} startedAt={startedAt} ambiguous={ambiguous} />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Realized P&L"
            value={formatCurrency(equity, 'INR')}
            highlight={equity > 0 ? 'up' : equity < 0 ? 'down' : undefined}
            hint="Realized gains/losses only. Does not reflect open-position price movement."
          />
          <MetricCard label="Open Positions" value={positionCount} />
          <MetricCard label="Total Fills" value={(fills || []).length} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <PositionsTable positions={positions} />
          <FillsTable fills={fills} />
        </div>
      </div>
    </Layout>
  );
};

export default Trading;
