import React from 'react';
import { Sheet } from '../doc/Doc';
import { Badge } from '../common/Badge';
import { formatNoteDate } from '../../utils/formatters';

const impactTone = (rating) => {
  if (rating >= 8) return 'destructive';
  if (rating >= 5) return 'warning';
  return 'secondary';
};

const EventsList = ({ events }) => {
  if (!events || events.length === 0) return null;

  return (
    <Sheet title="Notable events" meta={`${events.length}`}>
      <ul>
        {events.map((event, index) => (
          <li
            key={`${event.event_type}-${index}`}
            className="py-3 border-b border-[var(--rule)] last:border-b-0"
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="field-label text-[var(--ink)]">{event.event_type}</span>
              <span className="doc-meta shrink-0">
                {event.date ? formatNoteDate(new Date(event.date)) : '—'}
              </span>
            </div>
            <p className="mt-1.5 text-sm text-[var(--ink-soft)] leading-relaxed">
              {event.description}
            </p>
            {typeof event.impact_rating === 'number' && (
              <div className="mt-2">
                <Badge variant={impactTone(event.impact_rating)}>
                  Impact {event.impact_rating}/10
                </Badge>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Sheet>
  );
};

export default EventsList;
