import apiClient from './client';
import { useQuery } from '@tanstack/react-query';

export interface DailySavings {
    date: string;
    savings_pln: number;
}

export const fetchDailySavings = async (nodeId: string, days: number = 7): Promise<DailySavings[]> => {
    const response = await apiClient.get<DailySavings[]>(`/stats/daily-savings/${nodeId}`, {
        params: { days }
    });
    return response.data;
};

export const useDailySavings = (nodeId: string, days: number = 7) => {
    return useQuery({
        queryKey: ['stats', 'daily-savings', nodeId, days],
        queryFn: () => fetchDailySavings(nodeId, days),
        refetchInterval: 60000, // Refresh every minute
        enabled: !!nodeId
    });
};
