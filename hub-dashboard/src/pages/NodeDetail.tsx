import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
    ArrowLeft,
    Battery,
    Zap,
    Activity,
    Clock,
    ShieldAlert,
    Play,
    RotateCcw,
    Settings as SettingsIcon,
    ChevronRight,
    TrendingDown,
    Wallet,
    BrainCircuit,
    History
} from 'lucide-react';
import {
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    AreaChart,
    Area
} from 'recharts';
import { useNodeTelemetry, useNodes } from '../api/queries';
import Skeleton from '../components/common/Skeleton';
import apiClient from '../api/client';
import AnalyticsChart from '../components/AnalyticsChart';
import { toast } from 'sonner';

const NodeDetail: React.FC = () => {
    const { nodeId } = useParams<{ nodeId: string }>();
    const { data: nodes } = useNodes();
    const { data: telemetry, isLoading: isTelemetryLoading } = useNodeTelemetry(nodeId || '', 50);
    const [isCommandLoading, setIsCommandLoading] = useState<string | null>(null);

    const node = nodes?.find(n => n.id === nodeId);
    const latest = telemetry?.[0]?.data;

    const handleCommand = async (command: string) => {
        setIsCommandLoading(command);
        try {
            const toastId = toast.loading(`Sending ${command}...`);
            await apiClient.post(`/nodes/${nodeId}/command`, {
                command: command,
                params: {}
            });
            toast.success(`${command} executed successfully`, { id: toastId });
        } catch (err) {
            toast.error(`Failed to execute ${command}`);
        } finally {
            setIsCommandLoading(null);
        }
    };

    if (!node && !isTelemetryLoading) {
        return (
            <div className="flex-center flex-col h-[60vh] glass rounded-3xl text-slate-400">
                <ShieldAlert size={48} className="mb-4 text-warning" />
                <h3 className="text-xl font-heading font-bold text-white">Node Not Found</h3>
                <p className="mt-2">The requested node ID does not exist or you lack permission.</p>
                <Link to="/nodes" className="mt-6 text-primary hover:underline font-bold">Return to Nodes</Link>
            </div>
        );
    }

    const chartData = telemetry?.map(t => ({
        time: new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        soc: t.data.battery.soc_percent,
        power: t.data.solar.power_w,
        voltage: t.data.battery.voltage
    })).reverse() || [];

    return (
        <div className="space-y-8 fade-in">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Link to="/nodes" className="p-2 glass rounded-xl text-slate-400 hover:text-white transition-all">
                        <ArrowLeft size={20} />
                    </Link>
                    <div>
                        <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">
                            <Link to="/" className="hover:text-primary transition-colors">Fleet</Link>
                            <ChevronRight size={12} />
                            <span>{node?.hardware_id}</span>
                        </div>
                        <h1 className="text-3xl font-heading font-bold text-main uppercase">{node?.name || 'Unnamed Node'}</h1>
                    </div>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={() => handleCommand('RESTART_AGENT')}
                        disabled={!!isCommandLoading}
                        className="flex items-center gap-2 px-4 py-2 glass rounded-xl text-sm font-bold text-dim hover:text-primary transition-all active:scale-95 disabled:opacity-50"
                    >
                        <RotateCcw size={16} />
                        <span>Restart</span>
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 glass rounded-xl text-sm font-bold text-dim hover:text-main transition-all active:scale-95">
                        <SettingsIcon size={16} />
                        <span>Settings</span>
                    </button>
                </div>
            </div>

            {/* High-Level Overview Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="glass p-6 rounded-3xl border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity">
                        <Battery size={64} />
                    </div>
                    <p className="text-xs font-bold text-dim uppercase mb-2">Battery SOC</p>
                    {isTelemetryLoading ? <Skeleton className="h-10 w-24" /> : (
                        <div className="flex items-baseline gap-2">
                            <span className="text-4xl font-heading font-bold text-main">
                                {latest?.battery.soc_percent.toFixed(1) || '--'}
                            </span>
                            <span className="text-dim font-bold">%</span>
                        </div>
                    )}
                </div>

                <div className="glass p-6 rounded-3xl border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity">
                        <Zap size={64} />
                    </div>
                    <p className="text-xs font-bold text-dim uppercase mb-2">Power Source</p>
                    {isTelemetryLoading ? <Skeleton className="h-10 w-24" /> : (
                        <div className="flex items-baseline gap-2">
                            <span className="text-4xl font-heading font-bold text-primary">
                                {latest?.solar.power_w.toFixed(0) || '--'}
                            </span>
                            <span className="text-dim font-bold">W</span>
                        </div>
                    )}
                </div>

                <div className="glass p-6 rounded-3xl border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity">
                        <Wallet size={64} />
                    </div>
                    <p className="text-xs font-bold text-dim uppercase mb-2">Energy Cost</p>
                    {isTelemetryLoading ? <Skeleton className="h-10 w-24" /> : (
                        <div className="flex items-baseline gap-2">
                            <span className="text-4xl font-heading font-bold text-secondary">
                                {latest?.grid?.current_price || '0.00'}
                            </span>
                            <span className="text-dim font-bold text-xs ml-1">PLN/kWh</span>
                        </div>
                    )}
                </div>

                <div className="glass p-6 rounded-3xl border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity">
                        <TrendingDown size={64} />
                    </div>
                    <p className="text-xs font-bold text-dim uppercase mb-2">Daily Savings</p>
                    {isTelemetryLoading ? <Skeleton className="h-10 w-24" /> : (
                        <div className="flex items-baseline gap-2">
                            <span className="text-4xl font-heading font-bold text-success">
                                {latest?.optimizer?.daily_savings_pln || '0.00'}
                            </span>
                            <span className="text-dim font-bold text-xs ml-1">PLN</span>
                        </div>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Main Charts Area */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="glass p-6 rounded-3xl border-white/5">
                        <div className="flex items-center justify-between mb-8">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-primary/10 rounded-lg text-primary">
                                    <History size={18} />
                                </div>
                                <h3 className="text-lg font-heading font-bold text-main">Performance Trends</h3>
                            </div>
                            <div className="flex gap-4">
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-primary" />
                                    <span className="text-[10px] font-bold text-dim uppercase">Solar W</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="h-2 w-2 rounded-full bg-secondary" />
                                    <span className="text-[10px] font-bold text-dim uppercase">SOC %</span>
                                </div>
                            </div>
                        </div>

                        <div className="h-[350px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={chartData}>
                                    <defs>
                                        <linearGradient id="colorSolar" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="colorSoc" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--secondary))" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="hsl(var(--secondary))" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" vertical={false} />
                                    <XAxis
                                        dataKey="time"
                                        stroke="hsl(var(--text-dim))"
                                        fontSize={10}
                                        tickMargin={10}
                                        axisLine={false}
                                        tickLine={false}
                                    />
                                    <YAxis hide />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: 'var(--glass-bg)',
                                            borderColor: 'var(--glass-border)',
                                            borderRadius: '16px',
                                            backdropFilter: 'blur(12px)',
                                            fontSize: '12px',
                                            color: 'var(--text-main)'
                                        }}
                                        itemStyle={{ color: 'var(--text-main)' }}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="power"
                                        stroke="hsl(var(--primary))"
                                        strokeWidth={3}
                                        fillOpacity={1}
                                        fill="url(#colorSolar)"
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="soc"
                                        stroke="hsl(var(--secondary))"
                                        strokeWidth={3}
                                        fillOpacity={1}
                                        fill="url(#colorSoc)"
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* NEW: Analytics Chart */}
                    <AnalyticsChart nodeId={nodeId || ''} />

                    {/* Decision Timeline */}
                    <div className="glass p-6 rounded-3xl border-white/5">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="p-2 bg-secondary/10 rounded-lg text-secondary">
                                <BrainCircuit size={18} />
                            </div>
                            <h3 className="text-lg font-heading font-bold text-main">AI Optimizer Decisions</h3>
                        </div>

                        <div className="space-y-4">
                            {isTelemetryLoading ? [1, 2].map(i => <Skeleton key={i} className="h-16 w-full" />) : (
                                telemetry?.slice(0, 5).map((t, i) => (
                                    <div key={i} className={`p-4 rounded-2xl border flex items-center justify-between transition-all hover:bg-white/5 ${i === 0 ? 'bg-primary/5 border-primary/20' : 'bg-transparent border-white/5'}`}>
                                        <div className="flex items-center gap-4">
                                            <div className={`p-2 rounded-xl ${i === 0 ? 'bg-primary text-slate-950' : 'bg-white/5 text-dim'}`}>
                                                <Clock size={16} />
                                            </div>
                                            <div>
                                                <p className="text-sm font-bold text-main">{t.data.optimizer?.latest_decision || "Performing routine optimization"}</p>
                                                <p className="text-[10px] font-bold text-dim uppercase tracking-widest">
                                                    {new Date(t.timestamp).toLocaleTimeString()} • {t.data.grid?.mode || "IDLE"}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="text-xs font-black text-dim opacity-40">#{telemetry.length - i}</div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* Command Panel */}
                <div className="space-y-6">
                    <div className="glass p-6 rounded-3xl border-white/5 h-full">
                        <h3 className="text-lg font-heading font-bold text-main mb-6">Command Center</h3>

                        <div className="space-y-6">
                            <div className="p-5 rounded-2xl bg-white/5 border border-white/5 flex flex-col gap-5 shadow-sm">
                                <div>
                                    <h4 className="text-sm font-bold text-main">Inverter Override</h4>
                                    <p className="text-xs text-dim mt-1">Manual state prioritization</p>
                                </div>
                                <div className="flex gap-3">
                                    <button
                                        onClick={() => handleCommand('FORCE_CHARGE')}
                                        disabled={!!isCommandLoading}
                                        className="flex-1 flex items-center justify-center gap-2 py-4 bg-primary/10 text-primary border border-primary/20 rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-primary hover:text-white transition-all disabled:opacity-50"
                                    >
                                        <Play size={16} />
                                        <span>Charge</span>
                                    </button>
                                    <button
                                        onClick={() => handleCommand('DISCHARGE')}
                                        disabled={!!isCommandLoading}
                                        className="flex-1 flex items-center justify-center gap-2 py-4 bg-secondary/10 text-secondary border border-secondary/20 rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-secondary hover:text-white transition-all disabled:opacity-50"
                                    >
                                        <Activity size={16} />
                                        <span>Discharge</span>
                                    </button>
                                </div>
                            </div>

                            <div className="p-5 rounded-2xl bg-white/5 border border-white/5 space-y-4 shadow-sm">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h4 className="text-sm font-bold text-main">Dynamic Strategy</h4>
                                        <p className="text-xs text-dim mt-0.5">Automated price-aware logic</p>
                                    </div>
                                    <div className="h-6 w-11 bg-primary rounded-full flex items-center px-1 transition-all">
                                        <div className="h-4 w-4 bg-white rounded-full ml-auto shadow-sm" />
                                    </div>
                                </div>
                                <div className="h-[1px] bg-white/5" />
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h4 className="text-sm font-bold text-main">Safety Lock</h4>
                                        <p className="text-xs text-dim mt-0.5">Prevent battery deep drain</p>
                                    </div>
                                    <div className="h-6 w-11 bg-slate-400 dark:bg-slate-700 rounded-full flex items-center px-1 transition-all">
                                        <div className="h-4 w-4 bg-white rounded-full shadow-sm" />
                                    </div>
                                </div>
                            </div>

                            <div className="p-6 rounded-3xl bg-secondary/10 border border-secondary/10 text-center">
                                <p className="text-[9px] font-black text-secondary uppercase tracking-[0.2em]">Efficiency Rating</p>
                                <p className="text-3xl font-heading font-black text-secondary mt-1">98.4<span className="text-sm">%</span></p>
                            </div>

                            {/* Fleet Config Card */}
                            <div className="p-5 rounded-2xl bg-white/5 border border-white/5 shadow-sm">
                                <div className="flex items-center justify-between mb-3">
                                    <h4 className="text-sm font-bold text-main">Fleet Config</h4>
                                    <span className="text-[9px] font-bold text-dim uppercase">Loop-back</span>
                                </div>
                                <div className="max-h-48 overflow-y-auto rounded-lg bg-slate-900 p-3">
                                    <pre className="text-[10px] text-slate-300 font-mono whitespace-pre-wrap">
                                        {latest?.optimizer?.reported_config
                                            ? JSON.stringify(latest.optimizer.reported_config, null, 2)
                                            : 'No configuration reported yet.'}
                                    </pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default NodeDetail;
