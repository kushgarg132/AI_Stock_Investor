import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { ArrowRight, Loader2 } from 'lucide-react';
import Layout from '../components/Layout';
import SmartSearch from '../components/dashboard/SmartSearch';
import PnlStatement from '../components/dashboard/PnlStatement';
import TradeLedger from '../components/dashboard/TradeLedger';
import Market from '../components/dashboard/Market';
import AnalysisCard from '../components/AnalysisCard';
import { Sheet, Empty } from '../components/doc/Doc';
import { Button } from '../components/common/Button';
import api, { endpoints } from '../utils/api';
import { stream } from '../lib/ws';
import { useTopic } from '../hooks/useStream';

/**
 * The statement. Everything the operator checks in a mid-session glance, in
 * the order they check it: what is my net, is anything waiting for me, what
 * am I holding.
 *
 * Analysis streams over the socket and replaces the sheet stack when a scrip
 * is enquired on, then returns to it.
 */
const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const [pnl, setPnl] = useState(null);
  const [pnlLoading, setPnlLoading] = useState(true);
  const [trades, setTrades] = useState([]);
  const [tradesLoading, setTradesLoading] = useState(true);
  const [tradesError, setTradesError] = useState(null);
  const [pending, setPending] = useState([]);

  const [analysis, setAnalysis] = useState(null);
  const [analysing, setAnalysing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  useEffect(() => {
    api
      .get(endpoints.analytics.pnl)
      .then((res) => setPnl(res.data))
      .catch(() => setPnl(null))
      .finally(() => setPnlLoading(false));

    api
      .get(endpoints.trading.trades())
      .then((res) => setTrades(res.data))
      .catch((err) => setTradesError(err?.response?.data?.detail || 'Could not reach the ledger'))
      .finally(() => setTradesLoading(false));

    api
      .get(endpoints.suggestions.list({ status: 'PENDING' }))
      .then((res) => setPending(res.data))
      .catch(() => setPending([]));
  }, []);

  // Live: the whole point is that none of this needs a refresh.
  useTopic('pnl', (message) => setPnl(message.data));
  useTopic('trades', () => {
    api
      .get(endpoints.trading.trades())
      .then((res) => setTrades(res.data))
      .catch(() => {});
  });
  useTopic('suggestions', (message) => {
    if (message.event === 'created') setPending((list) => [message.data, ...list]);
    if (message.event === 'decided') {
      setPending((list) => list.filter((item) => item.id !== message.data.id));
    }
  });

  const analyse = (symbol) => {
    setAnalysing(true);
    setAnalysisError(null);
    setAnalysis(null);

    const request = stream.request('analyze', { symbol }, (message) => {
      if (message.event === 'report') {
        setAnalysis(message.data);
        setAnalysing(false);
      } else if (message.event === 'error') {
        setAnalysisError(message.data.detail);
        setAnalysing(false);
      }
    });

    // The socket may not be up (first paint, a dropped connection); the HTTP
    // route is the same analysis, just without the progress.
    if (!request.ok) {
      api
        .post(endpoints.analyze(symbol))
        .then((res) => setAnalysis(res.data))
        .catch((err) => setAnalysisError(err?.response?.data?.detail || 'Analysis failed'))
        .finally(() => setAnalysing(false));
    }
  };

  // Arriving from the watchlist or scanner with a symbol in hand.
  useEffect(() => {
    if (location.state?.symbol) {
      analyse(location.state.symbol);
      navigate('.', { replace: true, state: {} });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state?.symbol]);

  return (
    <Layout>
      <div className="space-y-4">
        <Sheet bodyClassName="p-4">
          <SmartSearch onSearch={analyse} isLoading={analysing} />
        </Sheet>

        {analysing && (
          <Sheet title="Enquiry in progress">
            <div className="flex items-center gap-3 py-6 justify-center text-[var(--ink-soft)]">
              <Loader2 className="w-4 h-4 animate-spin text-[var(--stamp)]" />
              <span className="text-sm">Reading fundamentals, news and technicals…</span>
            </div>
          </Sheet>
        )}

        {analysisError && (
          <Sheet title="Enquiry failed">
            <Empty
              title={analysisError}
              detail="The scrip may not be in the instrument master, or the data provider is unreachable."
            />
          </Sheet>
        )}

        {analysis && !analysing && (
          <div className="space-y-4">
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => setAnalysis(null)}>
                Back to statement
              </Button>
            </div>
            <AnalysisCard data={analysis} />
          </div>
        )}

        {!analysis && !analysing && (
          <>
            {pending.length > 0 && (
              <Link
                to="/suggestions"
                className="block sheet px-4 py-3.5 border-[var(--stamp)] hover:bg-[var(--stamp-soft)] transition-colors"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="field-label text-[var(--stamp)]">Awaiting your decision</p>
                    <p className="mt-1 text-sm text-[var(--ink)] truncate">
                      {pending.length} {pending.length === 1 ? 'proposal' : 'proposals'} ·{' '}
                      {pending
                        .slice(0, 3)
                        .map((item) => item.symbol)
                        .join(', ')}
                      {pending.length > 3 && ` +${pending.length - 3}`}
                    </p>
                  </div>
                  <ArrowRight className="w-5 h-5 shrink-0 text-[var(--stamp)]" />
                </div>
              </Link>
            )}

            <PnlStatement pnl={pnl} loading={pnlLoading} />

            <TradeLedger trades={trades} loading={tradesLoading} error={tradesError} />

            <Market />
          </>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
