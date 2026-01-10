import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { motion } from 'framer-motion';
import { Mail, Lock, LogIn, Activity, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import apiClient from '../api/client';
import { toast } from 'sonner';

const loginSchema = z.object({
    email: z.string().email('Invalid email address'),
    password: z.string().min(6, 'Password must be at least 6 characters'),
});

type LoginForm = z.infer<typeof loginSchema>;

const Login: React.FC = () => {
    const { login } = useAuth();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
        resolver: zodResolver(loginSchema),
    });

    const onSubmit = async (data: LoginForm) => {
        setIsSubmitting(true);
        setError(null);
        try {
            // API request to Hub Backend
            const formData = new FormData();
            formData.append('username', data.email);
            formData.append('password', data.password);

            const response = await apiClient.post('/auth/token', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const { access_token } = response.data;

            // Save token temporarily for subsequent request
            localStorage.setItem('token', access_token);

            // Get User Profile from /auth/me
            const profileResponse = await apiClient.get('/auth/me');
            const userProfile = profileResponse.data;

            login(access_token, userProfile);
            toast.success('Successfully logged in!');
        } catch (err: any) {
            console.error(err);
            setError('Invalid email or password. Please try again.');
            toast.error('Authentication failed');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-slate-950">
            {/* Background Glows */}
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 rounded-full blur-[120px]" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-secondary/10 rounded-full blur-[120px]" />

            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="w-full max-w-md"
            >
                <div className="glass p-8 rounded-3xl relative z-10 border-white/5 shadow-2xl">
                    <div className="flex flex-col items-center mb-8">
                        <div className="p-4 bg-primary/10 rounded-2xl text-primary mb-4 shadow-[0_0_20px_rgba(14,165,233,0.2)]">
                            <Activity size={32} />
                        </div>
                        <h1 className="text-3xl font-heading font-bold text-white tracking-tight">Welcome Back</h1>
                        <p className="text-slate-400 mt-2">Sign in to your GoodWe control panel</p>
                    </div>

                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
                        {error && (
                            <motion.div
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="p-4 bg-error/10 border border-error/20 rounded-xl flex items-center gap-3 text-error text-sm font-medium"
                            >
                                <AlertCircle size={18} />
                                <span>{error}</span>
                            </motion.div>
                        )}

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest ml-1">Email Address</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-500 group-focus-within:text-primary transition-colors">
                                    <Mail size={18} />
                                </div>
                                <input
                                    {...register('email')}
                                    type="email"
                                    placeholder="admin@example.com"
                                    className={`
                    w-full pl-11 pr-4 py-4 bg-slate-900/50 border rounded-2xl outline-none transition-all
                    focus:ring-2 focus:ring-primary/20 focus:bg-slate-900/80
                    ${errors.email ? 'border-error/50' : 'border-white/5 focus:border-primary/50'}
                  `}
                                />
                            </div>
                            {errors.email && <p className="text-error text-xs mt-1 ml-1">{errors.email.message}</p>}
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest ml-1">Password</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-500 group-focus-within:text-primary transition-colors">
                                    <Lock size={18} />
                                </div>
                                <input
                                    {...register('password')}
                                    type="password"
                                    placeholder="••••••••"
                                    className={`
                    w-full pl-11 pr-4 py-4 bg-slate-900/50 border rounded-2xl outline-none transition-all
                    focus:ring-2 focus:ring-primary/20 focus:bg-slate-900/80
                    ${errors.password ? 'border-error/50' : 'border-white/5 focus:border-primary/50'}
                  `}
                                />
                            </div>
                            {errors.password && <p className="text-error text-xs mt-1 ml-1">{errors.password.message}</p>}
                        </div>

                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className={`
                w-full py-4 rounded-2xl bg-primary text-slate-950 font-bold text-lg 
                shadow-[0_0_20px_rgba(14,165,233,0.3)] hover:shadow-[0_0_30px_rgba(14,165,233,0.5)] 
                hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-2
                ${isSubmitting ? 'opacity-70 cursor-not-allowed' : ''}
              `}
                        >
                            {isSubmitting ? (
                                <div className="h-5 w-5 border-2 border-slate-950/20 border-t-slate-950 rounded-full animate-spin" />
                            ) : (
                                <>
                                    <span>Sign In</span>
                                    <LogIn size={20} />
                                </>
                            )}
                        </button>
                    </form>

                    <div className="mt-10 pt-6 border-t border-white/5 text-center">
                        <p className="text-sm text-slate-500">
                            Need technical support? <a href="#" className="text-primary hover:underline font-medium">Contact Admin</a>
                        </p>
                    </div>
                </div>
            </motion.div>
        </div>
    );
};

export default Login;
