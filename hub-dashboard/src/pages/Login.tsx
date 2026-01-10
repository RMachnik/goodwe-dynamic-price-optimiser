import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { motion } from 'framer-motion';
import { Mail, Lock, LogIn, Activity, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import apiClient from '../api/client';
import { toast } from 'sonner';

// UI Components
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';

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
            const formData = new FormData();
            formData.append('username', data.email);
            formData.append('password', data.password);

            const response = await apiClient.post('/auth/token', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const { access_token } = response.data;
            localStorage.setItem('token', access_token);

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
        <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-background">
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 rounded-full blur-[120px]" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-secondary/10 rounded-full blur-[120px]" />

            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="w-full max-w-md z-10"
            >
                <Card className="border-border shadow-2xl">
                    <CardHeader className="items-center text-center pb-2">
                        <div className="p-4 bg-primary/10 rounded-2xl text-primary mb-4 shadow-[0_0_20px_rgba(14,165,233,0.2)]">
                            <Activity size={32} />
                        </div>
                        <CardTitle className="text-3xl">Welcome Back</CardTitle>
                        <p className="text-muted-foreground text-sm mt-2">Sign in to your GoodWe control panel</p>
                    </CardHeader>
                    <CardContent>
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
                                <label className="text-xs font-bold text-muted-foreground uppercase tracking-widest ml-1">Email Address</label>
                                <Input
                                    {...register('email')}
                                    type="email"
                                    placeholder="admin@example.com"
                                    icon={<Mail size={18} />}
                                    className={errors.email ? 'border-error/50' : ''}
                                />
                                {errors.email && <p className="text-error text-xs mt-1 ml-1">{errors.email.message}</p>}
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-muted-foreground uppercase tracking-widest ml-1">Password</label>
                                <Input
                                    {...register('password')}
                                    type="password"
                                    placeholder="••••••••"
                                    icon={<Lock size={18} />}
                                    className={errors.password ? 'border-error/50' : ''}
                                />
                                {errors.password && <p className="text-error text-xs mt-1 ml-1">{errors.password.message}</p>}
                            </div>

                            <Button
                                type="submit"
                                className="w-full h-14 text-lg"
                                isLoading={isSubmitting}
                            >
                                <span className="mr-2">Sign In</span>
                                {!isSubmitting && <LogIn size={20} />}
                            </Button>
                        </form>

                        <div className="mt-8 pt-6 border-t border-border text-center">
                            <p className="text-xs text-muted-foreground">
                                Need technical support? <a href="#" className="text-primary hover:underline font-bold">Contact Admin</a>
                            </p>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    );
};

export default Login;
