import React, { useMemo, useState } from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
    ReferenceLine
} from 'recharts';
import { useMarketPrices } from '../api/queries';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { DollarSign, TrendingDown, TrendingUp } from 'lucide-react';
import Skeleton from './common/Skeleton';

type DayFilter = 'all' | 'yesterday' | 'today' | 'tomorrow';

const MarketPriceChart: React.FC = () => {
    const { data: prices, isLoading } = useMarketPrices();
    const [dayFilter, setDayFilter] = useState<DayFilter>('all');

    // Filter prices based on selected day
    const filteredPrices = useMemo(() => {
        if (!prices || prices.length === 0) return [];
        if (dayFilter === 'all') return prices;

        return prices.filter(p => {
            const d = new Date(p.timestamp);
            if (dayFilter === 'yesterday') return isYesterday(d);
            if (dayFilter === 'today') return isToday(d);
            if (dayFilter === 'tomorrow') return isTomorrow(d);
            return true;
        });
    }, [prices, dayFilter]);

    // Calculate min/max for filtered prices
    const { minPrice, maxPrice, minIdx, maxIdx } = useMemo(() => {
        if (!filteredPrices || filteredPrices.length === 0) return { minPrice: 0, maxPrice: 0, minIdx: -1, maxIdx: -1 };

        let min = Infinity, max = -Infinity, minI = 0, maxI = 0;

        filteredPrices.forEach((p, i) => {
            if (p.price_pln_kwh < min) { min = p.price_pln_kwh; minI = i; }
            if (p.price_pln_kwh > max) { max = p.price_pln_kwh; maxI = i; }
        });

        return { minPrice: min, maxPrice: max, minIdx: minI, maxIdx: maxI };
    }, [filteredPrices]);

    // Day boundaries for reference lines (only in 'all' view)
    const dayBoundaries = useMemo(() => {
        if (!prices || prices.length === 0 || dayFilter !== 'all') return [];

        const boundaries: { x: string; label: string }[] = [];
        prices.forEach((p) => {
            const d = new Date(p.timestamp);
            if (d.getHours() === 0) {
                const dayLabel = isToday(d) ? 'Today' : isTomorrow(d) ? 'Tomorrow' : isYesterday(d) ? 'Yesterday' : d.toLocaleDateString([], { weekday: 'short', day: 'numeric' });
                boundaries.push({ x: p.timestamp, label: dayLabel });
            }
        });
        return boundaries;
    }, [prices, dayFilter]);

    if (isLoading) {
        return <Skeleton className="h-[300px] w-full rounded-3xl" />;
    }

    if (!prices || prices.length === 0) {
        return null;
    }

    const tabs: { key: DayFilter; label: string }[] = [
        { key: 'all', label: 'All' },
        { key: 'yesterday', label: 'Yesterday' },
        { key: 'today', label: 'Today' },
        { key: 'tomorrow', label: 'Tomorrow' },
    ];

    return (
        <Card className="border-border shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg text-primary">
                        <DollarSign size={18} />
                    </div>
                    <div>
                        <CardTitle className="text-lg">Market Prices (Day Ahead)</CardTitle>
                        <p className="text-xs text-muted-foreground">PLN/kWh</p>
                    </div>
                </div>
                {/* Min/Max Legend */}
                <div className="flex gap-4 text-xs">
                    <div className="flex items-center gap-1">
                        <TrendingDown size={14} className="text-success" />
                        <span className="text-muted-foreground">Min: </span>
                        <span className="font-semibold text-success">{minPrice.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <TrendingUp size={14} className="text-error" />
                        <span className="text-muted-foreground">Max: </span>
                        <span className="font-semibold text-error">{maxPrice.toFixed(2)}</span>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {/* Day Filter Tabs */}
                <div className="flex gap-1 mb-4 p-1 bg-muted/30 rounded-lg w-fit">
                    {tabs.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setDayFilter(tab.key)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${dayFilter === tab.key
                                ? 'bg-primary text-primary-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {filteredPrices.length === 0 ? (
                    <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                        No price data available for this day
                    </div>
                ) : (
                    <div className="h-[220px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={filteredPrices} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.1)" vertical={false} />

                                {/* Day Boundary Vertical Lines (only in 'all' view) */}
                                {dayFilter === 'all' && dayBoundaries.map((b, i) => (
                                    <ReferenceLine
                                        key={i}
                                        x={b.x}
                                        stroke="rgba(255,255,255,0.3)"
                                        strokeWidth={2}
                                        strokeDasharray="4 4"
                                        label={{ value: b.label, position: 'top', fontSize: 10, fill: 'rgba(255,255,255,0.5)' }}
                                    />
                                ))}

                                <XAxis
                                    dataKey="timestamp"
                                    stroke="hsl(var(--text-dim))"
                                    fontSize={11}
                                    tickFormatter={(val) => {
                                        const d = new Date(val);
                                        const hour = d.getHours();
                                        return `${hour.toString().padStart(2, '0')}:00`;
                                    }}
                                    axisLine={false}
                                    tickLine={false}
                                    interval={dayFilter === 'all' ? 5 : 2}
                                />
                                <YAxis
                                    hide
                                    domain={[0, 'auto']}
                                />
                                <Tooltip
                                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                    contentStyle={{
                                        backgroundColor: 'rgba(30,30,40,0.95)',
                                        borderColor: 'rgba(255,255,255,0.1)',
                                        borderRadius: '12px',
                                        backdropFilter: 'blur(12px)',
                                        fontSize: '12px',
                                        color: '#fff',
                                        boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
                                    }}
                                    formatter={(value: number | undefined) => [`${(value || 0).toFixed(2)} PLN/kWh`, 'Price']}
                                    labelFormatter={(label) => {
                                        const d = new Date(label);
                                        const dayName = isToday(d) ? 'Today' : isTomorrow(d) ? 'Tomorrow' : isYesterday(d) ? 'Yesterday' : d.toLocaleDateString([], { weekday: 'short' });
                                        return `${dayName}, ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
                                    }}
                                />
                                <Bar dataKey="price_pln_kwh" radius={[3, 3, 0, 0]}>
                                    {filteredPrices.map((entry, index) => {
                                        let fill = 'hsl(var(--primary))';
                                        let opacity = 0.7;

                                        if (index === maxIdx) {
                                            fill = 'hsl(var(--error))';
                                            opacity = 1;
                                        } else if (index === minIdx) {
                                            fill = 'hsl(var(--success))';
                                            opacity = 1;
                                        } else if (entry.price_pln_kwh > 0.70) {
                                            fill = 'hsl(var(--error))';
                                        } else if (entry.price_pln_kwh < 0.35) {
                                            fill = 'hsl(var(--success))';
                                        }

                                        return (
                                            <Cell
                                                key={`cell-${index}`}
                                                fill={fill}
                                                fillOpacity={opacity}
                                            />
                                        );
                                    })}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

// Helper functions
function isToday(d: Date): boolean {
    const today = new Date();
    return d.getDate() === today.getDate() && d.getMonth() === today.getMonth() && d.getFullYear() === today.getFullYear();
}

function isTomorrow(d: Date): boolean {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return d.getDate() === tomorrow.getDate() && d.getMonth() === tomorrow.getMonth() && d.getFullYear() === tomorrow.getFullYear();
}

function isYesterday(d: Date): boolean {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return d.getDate() === yesterday.getDate() && d.getMonth() === yesterday.getMonth() && d.getFullYear() === yesterday.getFullYear();
}

export default MarketPriceChart;
