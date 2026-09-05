import { useCallback, useEffect, useState } from 'react';
import api, { endpoints } from '../utils/api';

const POLL_INTERVAL_MS = 5000;

/**
 * Polls /trading/positions, /trading/fills, /trading/equity together on a
 * fixed client-side interval, decoupled from the backend run's own
 * poll_interval_seconds (that controls strategy re-evaluation server-side,
 * a separate concern from the UI refreshing its read view). Only polls
 * while `active` is true, and pauses while the tab is hidden.
 */
export function useTradingPoll(active) {
  const [positions, setPositions] = useState({});
  const [fills, setFills] = useState([]);
  const [equity, setEquity] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [positionsRes, fillsRes, equityRes] = await Promise.all([
        api.get(endpoints.trading.positions),
        api.get(endpoints.trading.fills),
        api.get(endpoints.trading.equity),
      ]);
      setPositions(positionsRes.data);
      setFills(fillsRes.data);
      setEquity(equityRes.data.equity);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch trading data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return undefined;

    fetchAll();
    const interval = setInterval(() => {
      if (!document.hidden) fetchAll();
    }, POLL_INTERVAL_MS);

    const onVisibilityChange = () => {
      if (!document.hidden) fetchAll();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [active, fetchAll]);

  return { positions, fills, equity, loading, error, lastUpdated };
}
