import React, { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import {
    LayoutDashboard,
    Users,
    Settings,
    LogOut,
    Menu,
    X,
    Activity,
    Cpu,
    Moon,
    Sun
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

const Layout: React.FC = () => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const location = useLocation();
    const { user, logout } = useAuth();
    const { theme, toggleTheme } = useTheme();

    const navItems = [
        { name: 'Dashboard', path: '/', icon: LayoutDashboard },
        { name: 'Nodes', path: '/nodes', icon: Cpu },
        { name: 'Admin', path: '/admin/users', icon: Users, adminOnly: true },
        { name: 'Settings', path: '/settings', icon: Settings },
    ];

    const filteredNavItems = navItems.filter(item =>
        !item.adminOnly || user?.role === 'admin'
    );

    return (
        <div className="min-h-screen flex bg-main text-main transition-colors duration-300">
            {/* Mobile Sidebar Toggle (Floating) */}
            <button
                className="fixed top-4 right-4 z-50 p-3 glass-card md:hidden mob-touch-target"
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                aria-label="Toggle Menu"
            >
                {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Sidebar (Desktop & Mobile Drawer) */}
            <aside className={`
        fixed inset-y-0 left-0 z-40 w-sidebar glass transform transition-transform duration-300 ease-in-out
        md:relative md:translate-x-0
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
                <div className="flex flex-col h-full p-6">
                    <div className="flex items-center gap-3 mb-10 px-2">
                        <div className="p-2.5 bg-primary/20 rounded-xl text-primary shadow-[0_0_15px_rgba(var(--primary),0.2)]">
                            <Activity size={24} />
                        </div>
                        <span className="font-heading font-bold text-xl tracking-tight">
                            GoodWe <span className="text-primary italic">Cloud</span>
                        </span>
                    </div>

                    <nav className="flex-1 space-y-2">
                        {filteredNavItems.map((item) => {
                            const Icon = item.icon;
                            const isActive = location.pathname === item.path;
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    onClick={() => setIsSidebarOpen(false)}
                                    className={`
                    flex items-center gap-3 px-4 py-3.5 rounded-2xl transition-all duration-200
                    ${isActive
                                            ? 'bg-primary/10 text-primary border border-primary/20 shadow-sm'
                                            : 'text-dim hover:text-main hover:bg-white/5'}
                  `}
                                >
                                    <Icon size={20} />
                                    <span className="font-semibold text-sm">{item.name}</span>
                                </Link>
                            );
                        })}
                    </nav>

                    <div className="mt-auto pt-6 border-t border-white/10 space-y-4">
                        {/* Theme Toggle */}
                        <button
                            onClick={toggleTheme}
                            className="w-full flex items-center justify-between px-4 py-3 bg-white/5 rounded-2xl text-dim hover:text-main transition-all"
                        >
                            <div className="flex items-center gap-3">
                                {theme === 'dark' ? <Moon size={18} /> : <Sun size={18} />}
                                <span className="text-sm font-medium">{theme === 'dark' ? 'Dark Mode' : 'Light Mode'}</span>
                            </div>
                            <div className={`w-10 h-5 rounded-full flex items-center px-1 transition-colors ${theme === 'dark' ? 'bg-primary/40' : 'bg-slate-300'}`}>
                                <div className={`w-3.5 h-3.5 bg-white rounded-full shadow-sm transition-transform ${theme === 'dark' ? 'translate-x-4.5' : 'translate-x-0'}`} />
                            </div>
                        </button>

                        <div className="px-4 py-2">
                            <p className="text-[10px] text-dim font-bold uppercase tracking-widest mb-1.5">Account</p>
                            <div className="flex items-center gap-3">
                                <div className="h-8 w-8 rounded-full bg-secondary/20 flex-center text-secondary font-bold text-xs uppercase">
                                    {user?.email?.[0]}
                                </div>
                                <div className="min-w-0">
                                    <p className="text-sm font-bold truncate">{user?.email}</p>
                                    <p className="text-[9px] text-primary font-bold uppercase tracking-tighter">{user?.role}</p>
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={logout}
                            className="w-full flex items-center gap-3 px-4 py-3 text-dim hover:text-error hover:bg-error/10 rounded-2xl transition-all font-semibold text-sm"
                        >
                            <LogOut size={20} />
                            <span>Sign Out</span>
                        </button>
                    </div>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
                <header className="h-16 flex items-center justify-between px-6 md:px-10 glass border-l-0 border-t-0 border-r-0 md:bg-transparent md:backdrop-filter-none md:border-none z-30">
                    <h2 className="text-xl font-heading font-bold text-main tracking-tight">
                        {navItems.find(i => i.path === location.pathname)?.name || 'Management'}
                    </h2>

                    <div className="md:hidden flex items-center gap-2">
                        <div className="p-2 bg-primary/20 rounded-lg text-primary">
                            <Activity size={18} />
                        </div>
                    </div>

                    <div className="hidden md:flex items-center gap-4">
                        {/* Desktop Search or Actions */}
                        <div className="px-4 py-1.5 bg-white/5 rounded-full text-[10px] font-bold text-dim uppercase tracking-widest border border-white/5">
                            Node Status: Online
                        </div>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-5 md:p-10 pb-24 md:pb-10">
                    <div className="max-w-7xl mx-auto page-enter">
                        <Outlet />
                    </div>
                </div>

                {/* Mobile Bottom Navigation */}
                <nav className="fixed bottom-0 left-0 right-0 h-mob-nav glass border-l-0 border-r-0 border-b-0 flex items-center justify-around md:hidden z-40 px-2 rounded-t-[32px]">
                    {filteredNavItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`
                            flex flex-col items-center gap-1 p-2 transition-all
                            ${isActive ? 'text-primary scale-110' : 'text-dim opacity-60'}
                        `}
                            >
                                <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
                                <span className="text-[10px] font-bold uppercase tracking-tighter">{item.name === 'User Management' ? 'Admin' : item.name}</span>
                            </Link>
                        );
                    })}
                </nav>
            </main>
        </div>
    );
};

export default Layout;
