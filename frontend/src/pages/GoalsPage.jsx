import React from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Target, TrendingUp, DollarSign, Calculator } from 'lucide-react';
import { formatCurrency } from '../utils/formatters';

const GoalsPage = () => {
  return (
    <Layout>
      <div className="space-y-8 animate-in fade-in duration-500">
        
        {/* Header */}
        <div>
            <h1 className="text-3xl font-bold tracking-tight mb-2">Financial Goals</h1>
            <p className="text-muted-foreground">Plan and track your wealth journey.</p>
        </div>

        {/* Goals Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <GoalCard 
                title="Retirement Fund"
                target={50000000}
                current={12500000}
                icon={Target}
                color="blue"
            />
            <GoalCard 
                title="New Home"
                target={15000000}
                current={4500000}
                icon={Calculator}
                color="purple"
            />
            <GoalCard 
                title="Emergency Fund"
                target={1000000}
                current={850000}
                icon={DollarSign}
                color="emerald"
            />
        </div>
        
        {/* Placeholder for Calculator */}
        <Card className="border-dashed border-2">
            <CardContent className="flex flex-col items-center justify-center h-64 text-center">
                 <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4">
                     <Calculator className="w-8 h-8 text-muted-foreground" />
                 </div>
                 <h3 className="text-lg font-semibold mb-1">SIP Calculator</h3>
                 <p className="text-muted-foreground">Interactive calculators coming in next update.</p>
            </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

const GoalCard = ({ title, target, current, icon: Icon, color }) => {
    const progress = (current / target) * 100;
    
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-lg font-medium">{title}</CardTitle>
                <div className={`p-2 rounded-lg bg-${color}-500/10 text-${color}-400`}>
                    <Icon className="w-5 h-5" />
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    <div className="flex justify-between items-end">
                        <div>
                            <p className="text-sm text-muted-foreground mb-1">Current</p>
                            <p className="text-2xl font-bold font-mono">{formatCurrency(current)}</p>
                        </div>
                        <div className="text-right">
                             <p className="text-sm text-muted-foreground mb-1">Target</p>
                             <p className="text-sm font-semibold">{formatCurrency(target)}</p>
                        </div>
                    </div>
                    
                    <div className="space-y-2">
                        <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                            <div 
                                className={`h-full bg-${color}-500 transition-all duration-1000`}
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                        <div className="flex justify-between text-xs text-muted-foreground">
                            <span>{progress.toFixed(1)}% Achieved</span>
                            <span>{formatCurrency(target - current)} remaining</span>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

export default GoalsPage;
