import React from 'react';
import { Card, CardContent } from '../common/Card';
import { Newspaper, ExternalLink, Clock } from 'lucide-react';
import { formatTimeAgo } from '../../utils/formatters';

const MarketNewsWidget = ({ articles, isLoading }) => {
    if (isLoading) {
        return (
            <div className="space-y-4 h-full">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    <Newspaper className="w-5 h-5 text-primary" /> Market Headlines
                </h3>
                <div className="space-y-4">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-20 bg-muted/20 animate-pulse rounded-lg" />
                    ))}
                </div>
            </div>
        );
    }

    if (!articles || articles.length === 0) return (
         <div className="text-center py-10 text-muted-foreground">No news available</div>
    );

    return (
        <div className="space-y-4 h-full">
            <h3 className="text-lg font-semibold flex items-center gap-2">
                <Newspaper className="w-5 h-5 text-primary" /> Market Headlines
            </h3>
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
                {articles.map((news, index) => (
                    <Card key={index} className="group hover:border-primary/30 transition-colors">
                        <CardContent className="p-4">
                            <a href={news.url} target="_blank" rel="noopener noreferrer" className="block">
                                <h4 className="font-medium group-hover:text-primary transition-colors line-clamp-2 mb-2">
                                    {news.title}
                                </h4>
                                <div className="flex items-center justify-between text-xs text-muted-foreground">
                                    <span className="flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {formatTimeAgo(news.published_at)}
                                    </span>
                                    <span className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        Read <ExternalLink className="w-3 h-3" />
                                    </span>
                                </div>
                                <div className="mt-2 text-xs font-semibold text-muted-foreground/50 uppercase">
                                    {news.source}
                                </div>
                            </a>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};

export default MarketNewsWidget;
