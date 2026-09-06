import React, { useState } from 'react';
import { Building2, BookmarkPlus, Check } from 'lucide-react';
import api, { endpoints } from '../utils/api';
import { Badge } from './common/Badge';
import { Button } from './common/Button';
import { Sheet, Field, Statement, Row, Cell } from './doc/Doc';
import {
  formatCurrency,
  formatCompactNumber,
  formatPercent,
  formatSignedPercent,
} from '../utils/formatters';
import { cn } from '../utils/cn';

import TradingChart from './stock/TradingChart';
import SentimentPanel from './analysis/SentimentPanel';
import RiskPanel from './analysis/RiskPanel';
import TechnicalPanel from './analysis/TechnicalPanel';
import NewsFeed from './analysis/NewsFeed';
import EventsList from './analysis/EventsList';

/**
 * A scrip enquiry, printed as a section of the note: the quotation at the
 * head, then fundamentals as a ruled schedule, then the analytical panels.
 */
const AnalysisCard = ({ data }) => {
  const [watched, setWatched] = useState(false);
  const [watchError, setWatchError] = useState(null);

  if (!data) return null;

  const {
    company_info: company,
    price_data: priceData,
    technical_analysis: technicals,
    sentiment_score: sentimentScore,
    analyst_summary: analystSummary,
    final_signal: finalSignal,
    all_signals: allSignals,
    indicators,
    risk,
    sentiment,
  } = data;

  const change = company?.day_change_percent || 0;
  const currency = company?.currency || 'INR';

  const addToWatchlist = async () => {
    setWatchError(null);
    try {
      await api.post(endpoints.watchlist.add(company?.symbol));
      setWatched(true);
    } catch (err) {
      setWatchError(err?.response?.data?.detail || 'Could not add to the watchlist');
    }
  };

  const schedule = [
    ['Market cap', formatCompactNumber(company?.market_cap)],
    ['Volume', formatCompactNumber(company?.volume)],
    ['P/E', typeof company?.pe_ratio === 'number' ? company.pe_ratio.toFixed(2) : '—'],
    ['PEG', company?.peg_ratio ?? '—'],
    ['52-week high', formatCurrency(company?.week_52_high, currency)],
    ['52-week low', formatCurrency(company?.week_52_low, currency)],
    ['Revenue growth', formatPercent((company?.revenue_growth ?? 0) * 100)],
    ['Return on equity', formatPercent((company?.return_on_equity ?? 0) * 100)],
  ];

  return (
    <div className="space-y-4">
      <Sheet bodyClassName="p-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-11 h-11 shrink-0 border border-[var(--rule-strong)] bg-[var(--paper-sunk)] flex items-center justify-center overflow-hidden">
              {company?.logo_url ? (
                <img
                  src={company.logo_url}
                  alt=""
                  className="w-full h-full object-contain p-1"
                />
              ) : (
                <Building2 className="w-5 h-5 text-[var(--ink-faint)]" aria-hidden="true" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="figure-md text-xl">{company?.symbol}</h2>
                {company?.sector && <Badge variant="outline">{company.sector}</Badge>}
              </div>
              <p className="text-sm text-[var(--ink-soft)] truncate">{company?.name}</p>
            </div>
          </div>

          <div className="text-right">
            <p className="figure-md text-2xl">
              {formatCurrency(company?.current_price, currency)}
            </p>
            <p className={cn('figure-md text-sm', change >= 0 ? 'text-up' : 'text-down')}>
              {formatSignedPercent(change)}{' '}
              <span className="text-[var(--ink-faint)]">today</span>
            </p>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-[var(--rule)] flex items-center justify-between gap-3">
          <span className="doc-meta">Enquiry</span>
          <Button variant="secondary" size="sm" onClick={addToWatchlist} disabled={watched}>
            {watched ? <Check className="w-3.5 h-3.5" /> : <BookmarkPlus className="w-3.5 h-3.5" />}
            {watched ? 'On watchlist' : 'Watch'}
          </Button>
        </div>
        {watchError && <p className="mt-2 text-sm text-[var(--loss)]">{watchError}</p>}
      </Sheet>

      <Sheet title="Price">
        <TradingChart data={priceData} technicals={technicals} currency={currency} />
      </Sheet>

      <Sheet title="Schedule of particulars">
        <Statement
          columns={[
            { key: 'item', label: 'Particular' },
            { key: 'value', label: 'Value', align: 'right' },
          ]}
        >
          {schedule.map(([label, value]) => (
            <Row key={label}>
              <Cell className="text-[var(--ink-soft)]">{label}</Cell>
              <Cell align="right" mono>
                {value}
              </Cell>
            </Row>
          ))}
        </Statement>
      </Sheet>

      <div className="grid gap-4 lg:grid-cols-3">
        <SentimentPanel
          score={sentiment?.score ?? sentimentScore}
          summary={analystSummary}
          sentiment={sentiment}
        />
        <RiskPanel signal={finalSignal} risk={risk} currency={currency} />
        <TechnicalPanel signals={allSignals} indicators={indicators} currency={currency} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <NewsFeed articles={data.news_articles} />
        <EventsList events={data.events} />
      </div>
    </div>
  );
};

export default AnalysisCard;
