import React from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell
} from 'recharts';
import { useDailySavings } from '../api/stats';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { TrendingUp } from 'lucide-react';
import Skeleton from './common/Skeleton';

interface AnalyticsChartProps {
    nodeId: string;
}

const AnalyticsChart: React.FC<AnalyticsChartProps> = ({ nodeId }) => {
    const { data: savings, isLoading } = useDailySavings(nodeId, 7);

    // Calculate total savings
    const totalSavings = savings?.reduce((acc, curr) => acc + curr.savings_pln, 0) || 0;

    if (isLoading) {
        return <Skeleton className="h-[300px] w-full rounded-3xl" />;
    }

    if (!savings || savings.length === 0) {
        return (
            <Card className="border-border shadow-sm">
                <CardHeader>
                    <CardTitle className="text-lg">Daily Savings Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-[200px] flex items-center justify-center text-muted-foreground">
                        No data available for analytics
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="border-border shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-success/10 rounded-lg text-success">
                        <TrendingUp size={18} />
                    </div>
                    <div>
                        <CardTitle className="text-lg">Cost Savings</CardTitle>
                        <p className="text-xs text-muted-foreground">Last 7 Days Performance</p>
                    </div>
                </div>
                <div className="text-right">
                    <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Total Saved</p>
                    <p className="text-2xl font-heading font-black text-success">
                        +{totalSavings.toFixed(2)} <span className="text-sm text-muted-foreground">PLN</span>
                    </p>
                </div>
            </CardHeader>
            <CardContent>
                <div className="h-[250px] w-full mt-4">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={savings}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" vertical={false} />
                            <XAxis
                                dataKey="date"
                                stroke="hsl(var(--text-dim))"
                                fontSize={10}
                                tickFormatter={(val) => new Date(val).toLocaleDateString(undefined, { weekday: 'short' })}
                                axisLine={false}
                                tickLine={false}
                            />
                            <YAxis hide />
                            <Tooltip
                                cursor={{ fill: 'var(--bg-main)', opacity: 0.5 }}
                                contentStyle={{
                                    backgroundColor: 'var(--glass-bg)',
                                    borderColor: 'var(--glass-border)',
                                    borderRadius: '12px',
                                    backdropFilter: 'blur(12px)',
                                    fontSize: '12px',
                                    color: 'var(--text-main)',
                                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                                }}
                            />
                            <Bar dataKey="savings_pln" radius={[6, 6, 0, 0]}>
                                {savings.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={entry.savings_pln >= 0 ? 'hsl(var(--success))' : 'hsl(var(--error))'}
                                        fillOpacity={0.8}
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
};

export default AnalyticsChart;
