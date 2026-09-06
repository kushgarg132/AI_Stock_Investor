import React from 'react';
import { ExternalLink } from 'lucide-react';
import { Sheet } from '../doc/Doc';
import { Badge } from '../common/Badge';
import { formatNoteDate } from '../../utils/formatters';

const tone = (sentiment) =>
  sentiment === 'positive' ? 'success' : sentiment === 'negative' ? 'destructive' : 'secondary';

const NewsFeed = ({ articles }) => {
  if (!articles || articles.length === 0) return null;

  return (
    <Sheet title="Press" meta={`${articles.length} filed`}>
      <ul>
        {articles.slice(0, 8).map((article, index) => (
          <li key={article.url || index} className="border-b border-[var(--rule)] last:border-b-0">
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group block py-3 hover:bg-[var(--paper-sunk)] -mx-2 px-2 transition-colors"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="doc-meta truncate">{article.source}</span>
                <span className="doc-meta shrink-0">
                  {article.published_at ? formatNoteDate(new Date(article.published_at)) : '—'}
                </span>
              </div>
              <p className="mt-1 text-sm leading-snug group-hover:underline decoration-[var(--stamp)] underline-offset-2">
                {article.title}
              </p>
              <div className="mt-2 flex items-center gap-2">
                {article.sentiment && (
                  <Badge variant={tone(article.sentiment)}>{article.sentiment}</Badge>
                )}
                <ExternalLink
                  className="w-3 h-3 text-[var(--ink-faint)] group-hover:text-[var(--stamp)] transition-colors"
                  aria-hidden="true"
                />
              </div>
            </a>
          </li>
        ))}
      </ul>
    </Sheet>
  );
};

export default NewsFeed;
