import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { BookMarked, Plus } from 'lucide-react';
import { Button } from '../common/Button';

const WatchlistWidget = () => {
    // Mock for now, will connect to Zustand later
    const watchlist = []; 

    return (
        <Card className="h-full">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                    <BookMarked className="w-4 h-4 text-purple-400" />
                    Your Watchlist
                </CardTitle>
                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 rounded-full">
                    <Plus className="w-4 h-4" />
                </Button>
            </CardHeader>
            <CardContent className="p-0">
                {watchlist.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="w-12 h-12 rounded-full bg-muted/50 flex items-center justify-center mb-3">
                            <BookMarked className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <p className="text-sm font-medium text-muted-foreground">No stocks watched yet</p>
                        <p className="text-xs text-muted-foreground/60 max-w-[150px] mt-1">Start searching to add stocks to your list.</p>
                    </div>
                ) : (
                    <div>{/* List Logic */}</div>
                )}
            </CardContent>
        </Card>
    );
};

export default WatchlistWidget;
