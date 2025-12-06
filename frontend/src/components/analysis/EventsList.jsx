import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Calendar, AlertTriangle } from 'lucide-react';

const EventsList = ({ events }) => {
    if (!events || events.length === 0) return null;

    return (
        <Card className="h-full">
            <CardHeader className="pb-4">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Calendar className="w-4 h-4 text-purple-400" />
                    Notable Events
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="relative border-l border-border ml-3 pl-6 space-y-6">
                    {events.map((event, idx) => (
                        <div key={idx} className="relative">
                            <div className="absolute -left-[31px] top-1 w-2.5 h-2.5 rounded-full bg-background border-2 border-purple-500" />
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-semibold text-foreground">{event.event_type}</span>
                                <span className="text-xs text-muted-foreground font-mono">{new Date(event.date).toLocaleDateString()}</span>
                            </div>
                            <p className="text-sm text-muted-foreground leading-relaxed mb-2">
                                {event.description}
                            </p>
                            <div className="flex items-center gap-2">
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                                    event.impact_rating >= 8 ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                                    event.impact_rating >= 5 ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                                    "bg-blue-500/10 text-blue-400 border-blue-500/20"
                                }`}>
                                    IMPACT: {event.impact_rating}/10
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

export default EventsList;
