import React from 'react';
import { Badge } from '../common/Badge';
import { AlertTriangle } from 'lucide-react';
import { formatTimeAgo } from '../../utils/formatters';

/**
 * Three explicit states, honest about what the backend can and can't tell us
 * (there is no GET /trading/status): Idle (nothing rendered), Active (we
 * hold a run_id we started ourselves), and Ambiguous (positions/fills exist
 * but we have no run_id -- e.g. cleared localStorage, a different tab/browser
 * started a run). Never implies a "reconnect" capability the API doesn't have.
 */
const RunStatusBanner = ({ runId, mode, startedAt, ambiguous }) => {
  if (!runId && !ambiguous) return null;

  if (ambiguous) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">
          Trading data exists but this browser has no record of starting a run. A run may still be
          active on the server -- this UI can't verify or stop a run it didn't start (no status
          endpoint exists yet).
        </p>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <Badge variant="success">Run active &middot; {mode}</Badge>
      {startedAt && (
        <span className="text-xs text-muted-foreground">started {formatTimeAgo(startedAt)}</span>
      )}
      <span className="text-xs text-muted-foreground font-mono">{runId.slice(0, 8)}&hellip;</span>
    </div>
  );
};

export default RunStatusBanner;
