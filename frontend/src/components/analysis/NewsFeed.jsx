import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Newspaper, ExternalLink } from 'lucide-react';
import { Badge } from '../common/Badge';

const NewsFeed = ({ articles }) => {
    if (!articles || articles.length === 0) return null;

    return (
        <Card>
            <CardHeader className="pb-4">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Newspaper className="w-4 h-4 text-blue-400" />
                    Latest News & Sentiment
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {articles.slice(0, 6).map((article, idx) => (
                        <a 
                            key={idx}
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex flex-col p-4 rounded-lg bg-muted/30 border border-border/50 hover:bg-muted/50 hover:border-primary/30 transition-all group h-full"
                        >
                            <div className="flex items-start justify-between gap-2 mb-2">
                                <span className="text-xs font-semibold text-muted-foreground">{article.source}</span>
                                <time className="text-xs text-muted-foreground/60">{new Date(article.published_at).toLocaleDateString()}</time>
                            </div>
                            <h4 className="font-medium text-sm leading-snug mb-3 line-clamp-2 group-hover:text-primary transition-colors">
                                {article.title}
                            </h4>
                            <div className="mt-auto flex items-center justify-between">
                                {article.sentiment && (
                                    <Badge variant={
                                        article.sentiment === 'positive' ? 'success' : 
                                        article.sentiment === 'negative' ? 'destructive' : 'warning'
                                    }>
                                        {article.sentiment}
                                    </Badge>
                                )}
                                <ExternalLink className="w-3 h-3 text-muted-foreground group-hover:text-primary opacity-0 group-hover:opacity-100 transition-all" />
                            </div>
                        </a>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

export default NewsFeed;
