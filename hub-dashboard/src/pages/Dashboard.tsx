import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Cpu, Wifi, WifiOff, Battery, Zap, Clock } from 'lucide-react';
import { useNodes } from '../api/queries';
import Skeleton from '../components/common/Skeleton';

import MarketPriceChart from '../components/MarketPriceChart';

const Dashboard: React.FC = () => {
    const { data: nodes, isLoading, error } = useNodes();
    const navigate = useNavigate();

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 fade-in">
                {[1, 2, 3].map(i => (
                    <div key={i} className="glass p-6 rounded-3xl h-48">
                        <Skeleton className="h-6 w-32 mb-4" />
                        <Skeleton className="h-4 w-full mb-2" />
                        <Skeleton className="h-4 w-2/3 mb-6" />
                        <div className="flex gap-4">
                            <Skeleton className="h-10 w-24 rounded-xl" />
                            <Skeleton className="h-10 w-24 rounded-xl" />
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex-center flex-col p-12 glass rounded-3xl text-slate-400">
                <WifiOff size={48} className="mb-4 text-error" />
                <h3 className="text-xl font-heading font-bold text-white">Connection Error</h3>
                <p className="mt-2">Unable to fetch nodes from the Hub API.</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 fade-in">
            <div className="flex items-end justify-between">
                <div>
                    <h1 className="text-3xl font-heading font-bold text-white">Fleet Overview</h1>
                    <p className="text-slate-400 mt-1">Monitoring {nodes?.length || 0} active edge nodes</p>
                </div>
                <div className="hidden md:flex gap-2">
                    <span className="px-3 py-1 rounded-full bg-success/10 text-success text-xs font-bold border border-success/20 flex items-center gap-1">
                        <div className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                        {nodes?.filter(n => n.is_online).length} Online
                    </span>
                    <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-400 text-xs font-bold border border-white/5 flex items-center gap-1">
                        {nodes?.filter(n => !n.is_online).length} Offline
                    </span>
                </div>
            </div>

            {/* Global Market Price Chart */}
            <div className="w-full">
                <MarketPriceChart />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {nodes?.map((node, index) => (
                    <motion.div
                        key={node.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        onClick={() => navigate(`/nodes/${node.id}`)}
                        className="group glass p-6 rounded-3xl glass-hover relative overflow-hidden cursor-pointer"
                    >
                        {/* Background Icon */}
                        <Cpu className="absolute -right-4 -bottom-4 text-white/5 group-hover:text-primary/10 transition-colors" size={120} />

                        <div className="flex items-start justify-between mb-6 relative z-10">
                            <div className="p-3 bg-white/5 rounded-2xl text-slate-300 group-hover:bg-primary/10 group-hover:text-primary transition-all">
                                <Cpu size={24} />
                            </div>
                            <div className={`
                flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider
                ${node.is_online ? 'bg-success/10 text-success border border-success/20' : 'bg-slate-800 text-slate-500 border border-white/5'}
              `}>
                                {node.is_online ? <Wifi size={12} /> : <WifiOff size={12} />}
                                {node.is_online ? 'Online' : 'Offline'}
                            </div>
                        </div>

                        <div className="relative z-10 mb-6">
                            <h3 className="text-xl font-heading font-bold text-white group-hover:text-primary transition-colors">{node.name || 'Unnamed Node'}</h3>
                            <p className="text-sm text-slate-500 font-mono tracking-tight mt-1">{node.hardware_id}</p>

                            {/* Config Badges */}
                            <div className="flex flex-wrap gap-2 mt-3">
                                {node.config?.tariff && (
                                    <span className="px-2 py-0.5 rounded-md bg-white/5 text-[10px] font-bold text-slate-400 border border-white/5 uppercase">
                                        {node.config.tariff}
                                    </span>
                                )}
                                {node.config?.pv_size_kw && (
                                    <span className="px-2 py-0.5 rounded-md bg-white/5 text-[10px] font-bold text-slate-400 border border-white/5 uppercase">
                                        PV: {node.config.pv_size_kw}kW
                                    </span>
                                )}
                                {node.config?.bat_capacity_kwh && (
                                    <span className="px-2 py-0.5 rounded-md bg-white/5 text-[10px] font-bold text-slate-400 border border-white/5 uppercase">
                                        Bat: {node.config.bat_capacity_kwh}kWh
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4 relative z-10 pt-4 border-t border-white/5">
                            <div className="flex items-center gap-3">
                                <div className="text-slate-500">
                                    <Battery size={18} />
                                </div>
                                <div>
                                    <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest">Battery</p>
                                    <p className="text-sm font-semibold text-slate-300">
                                        {node.latest_telemetry?.battery?.soc_percent !== undefined
                                            ? `${node.latest_telemetry.battery.soc_percent.toFixed(1)} %`
                                            : '-- %'}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="text-slate-500">
                                    <Zap size={18} />
                                </div>
                                <div>
                                    <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest">Solar</p>
                                    <p className="text-sm font-semibold text-slate-300">
                                        {node.latest_telemetry?.solar?.power_w !== undefined
                                            ? `${node.latest_telemetry.solar.power_w.toFixed(0)} W`
                                            : '-- W'}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <div className="mt-6 flex items-center justify-between relative z-10">
                            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
                                <Clock size={12} />
                                <span>{node.last_seen ? new Date(node.last_seen).toLocaleTimeString() : 'Never'}</span>
                            </div>
                            <button
                                className="text-xs font-bold text-primary hover:text-white transition-colors uppercase tracking-widest"
                            >
                                Details →
                            </button>
                        </div>
                    </motion.div>
                ))}

                {nodes?.length === 0 && (
                    <div className="col-span-full py-20 flex-center flex-col glass rounded-3xl text-slate-500">
                        <Cpu size={48} className="mb-4 opacity-20" />
                        <p className="text-lg">No nodes enrolled yet.</p>
                        <button className="mt-4 px-6 py-2 bg-primary/10 text-primary border border-primary/20 rounded-xl font-bold hover:bg-primary hover:text-slate-950 transition-all">
                            Enroll First Node
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Dashboard;
