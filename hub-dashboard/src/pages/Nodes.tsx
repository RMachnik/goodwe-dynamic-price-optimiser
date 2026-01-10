import React from 'react';
import { motion } from 'framer-motion';
import {
    Wifi,
    WifiOff,
    MoreVertical,
    RefreshCcw,
    Trash2,
    Settings,
    Plus
} from 'lucide-react';
import { useNodes } from '../api/queries';
import Skeleton from '../components/common/Skeleton';

const Nodes: React.FC = () => {
    const { data: nodes, isLoading } = useNodes();

    return (
        <div className="space-y-8 fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-heading font-bold text-white">Node Management</h1>
                    <p className="text-slate-400 mt-1">Configure and manage your IoT fleet</p>
                </div>
                <button className="flex items-center gap-2 px-6 py-3 bg-primary text-slate-950 rounded-2xl font-bold shadow-lg hover:shadow-primary/20 hover:scale-[1.02] transition-all">
                    <Plus size={20} />
                    <span>Enroll New Node</span>
                </button>
            </div>

            <div className="glass rounded-3xl overflow-hidden border-white/5 shadow-2xl">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-white/5 border-b border-white/10">
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Hardware ID</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Name</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Status</th>
                            <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Last Seen</th>
                            <th className="px-6 py-4 text-right text-xs font-bold text-slate-500 uppercase tracking-widest">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                        {isLoading ? (
                            [1, 2, 3, 4, 5].map(i => (
                                <tr key={i} className="animate-pulse">
                                    <td className="px-6 py-5"><Skeleton className="h-4 w-32" /></td>
                                    <td className="px-6 py-5"><Skeleton className="h-4 w-24" /></td>
                                    <td className="px-6 py-5"><Skeleton className="h-6 w-20 rounded-full" /></td>
                                    <td className="px-6 py-5"><Skeleton className="h-4 w-28" /></td>
                                    <td className="px-6 py-5 text-right"><Skeleton className="h-8 w-8 rounded-lg ml-auto" /></td>
                                </tr>
                            ))
                        ) : (
                            nodes?.map((node, index) => (
                                <motion.tr
                                    key={node.id}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    className="group hover:bg-white/[0.02] transition-colors"
                                >
                                    <td className="px-6 py-5">
                                        <span className="font-mono text-sm text-slate-300 group-hover:text-primary transition-colors">
                                            {node.hardware_id}
                                        </span>
                                    </td>
                                    <td className="px-6 py-5">
                                        <span className="font-semibold text-slate-200">{node.name || '—'}</span>
                                    </td>
                                    <td className="px-6 py-5">
                                        <div className={`
                      inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider
                      ${node.is_online ? 'bg-success/10 text-success' : 'bg-slate-800 text-slate-500'}
                    `}>
                                            {node.is_online ? <Wifi size={12} /> : <WifiOff size={12} />}
                                            {node.is_online ? 'Online' : 'Offline'}
                                        </div>
                                    </td>
                                    <td className="px-6 py-5">
                                        <span className="text-sm text-slate-500">
                                            {node.last_seen ? new Date(node.last_seen).toLocaleString() : 'Never'}
                                        </span>
                                    </td>
                                    <td className="px-6 py-5 text-right">
                                        <div className="flex items-center justify-end gap-2">
                                            <button title="Restart" className="p-2 text-slate-500 hover:text-primary hover:bg-primary/10 rounded-lg transition-all">
                                                <RefreshCcw size={18} />
                                            </button>
                                            <button title="Configure" className="p-2 text-slate-500 hover:text-slate-200 hover:bg-white/10 rounded-lg transition-all">
                                                <Settings size={18} />
                                            </button>
                                            <button title="Delete" className="p-2 text-slate-500 hover:text-error hover:bg-error/10 rounded-lg transition-all">
                                                <Trash2 size={18} />
                                            </button>
                                            <div className="w-px h-4 bg-white/10 mx-1" />
                                            <button className="p-2 text-slate-500 hover:text-white hover:bg-white/10 rounded-lg transition-all">
                                                <MoreVertical size={18} />
                                            </button>
                                        </div>
                                    </td>
                                </motion.tr>
                            ))
                        )}
                    </tbody>
                </table>

                {!isLoading && nodes?.length === 0 && (
                    <div className="p-20 text-center text-slate-500">
                        <p className="text-lg">No nodes found in the system.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Nodes;
