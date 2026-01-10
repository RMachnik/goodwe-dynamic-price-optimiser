import React from 'react';
import { motion } from 'framer-motion';
import {
    UserPlus,
    Mail,
    Shield,
    Trash2,
    Edit,
    User as UserIcon
} from 'lucide-react';
import Skeleton from '../components/common/Skeleton';

// Mock Users (to be replaced with actual API call)
const mockUsers = [
    { id: '1', email: 'admin@example.com', role: 'admin', created_at: '2023-10-01' },
    { id: '2', email: 'user@example.com', role: 'user', created_at: '2023-10-05' },
];

const AdminUsers: React.FC = () => {
    // const { data: users, isLoading } = useUsers(); // Future Hook

    const isLoading = false;
    const users = mockUsers;

    return (
        <div className="space-y-8 fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-heading font-bold text-white">User Management</h1>
                    <p className="text-slate-400 mt-1">Control access and roles for the platform</p>
                </div>
                <button className="flex items-center gap-2 px-6 py-3 bg-secondary text-white rounded-2xl font-bold shadow-lg hover:shadow-secondary/20 hover:scale-[1.02] transition-all">
                    <UserPlus size={20} />
                    <span>Invite User</span>
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {isLoading ? (
                    [1, 2].map(i => (
                        <div key={i} className="glass p-6 rounded-3xl h-32 animate-pulse">
                            <Skeleton className="h-4 w-48 mb-4" />
                            <Skeleton className="h-4 w-24" />
                        </div>
                    ))
                ) : (
                    users.map((u, index) => (
                        <motion.div
                            key={u.id}
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: index * 0.1 }}
                            className="glass p-6 rounded-3xl border-white/5 flex items-center gap-6 relative group overflow-hidden"
                        >
                            <div className={`
                p-4 rounded-2xl flex-shrink-0 transition-colors
                ${u.role === 'admin' ? 'bg-secondary/20 text-secondary' : 'bg-primary/20 text-primary'}
              `}>
                                <UserIcon size={32} />
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <h3 className="text-lg font-bold text-white truncate">{u.email}</h3>
                                    {u.role === 'admin' && (
                                        <span className="px-2 py-0.5 rounded-md bg-secondary/10 text-secondary text-[10px] font-black uppercase border border-secondary/20">
                                            Admin
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-4 text-xs text-slate-500">
                                    <span className="flex items-center gap-1.5"><Mail size={12} /> {u.email}</span>
                                    <span className="flex items-center gap-1.5"><Shield size={12} /> {u.role}</span>
                                </div>
                            </div>

                            <div className="flex flex-col gap-2">
                                <button title="Edit User" className="p-2 text-slate-500 hover:text-white hover:bg-white/10 rounded-xl transition-all">
                                    <Edit size={18} />
                                </button>
                                <button title="Delete User" className="p-2 text-slate-500 hover:text-error hover:bg-error/10 rounded-xl transition-all">
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        </motion.div>
                    ))
                )}
            </div>

            <div className="p-8 glass rounded-3xl border-dashed border-2 border-white/5 flex flex-col items-center justify-center text-slate-500">
                <p className="text-sm font-medium">Security Note: Admin accounts have full access to all nodes and commands.</p>
            </div>
        </div>
    );
};

export default AdminUsers;
