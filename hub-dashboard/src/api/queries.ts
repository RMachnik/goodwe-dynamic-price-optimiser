import { useQuery } from '@tanstack/react-query';
import apiClient from './client';

export interface Node {
    id: string;
    hardware_id: string;
    name: string;
    is_online: boolean;
    last_seen: string;
    config?: {
        tariff?: string;
        pv_size_kw?: number;
        bat_capacity_kwh?: number;
        [key: string]: any;
    };
    latest_telemetry?: Telemetry['data'];
}

export interface Telemetry {
    timestamp: string;
    data: {
        battery: {
            soc_percent: number;
            voltage: number;
        };
        solar: {
            power_w: number;
        };
        grid?: {
            current_price: number;
            mode: string;
        };
        optimizer?: {
            latest_decision: string;
            daily_savings_pln: number;
            daily_cost_pln: number;
            reported_config?: Record<string, any>;
        };
        node_id: string;
    };
}

// Fetch all nodes
export const useNodes = () => {
    return useQuery<Node[]>({
        queryKey: ['nodes'],
        queryFn: async () => {
            const { data } = await apiClient.get('/nodes/');
            return data;
        },
    });
};

// Fetch telemetry for a specific node
export const useNodeTelemetry = (nodeId: string, limit: number = 20) => {
    return useQuery<Telemetry[]>({
        queryKey: ['nodes', nodeId, 'telemetry', limit],
        queryFn: async () => {
            const { data } = await apiClient.get(`/nodes/${nodeId}/telemetry?limit=${limit}`);
            return data;
        },
        enabled: !!nodeId,
        refetchInterval: 5000,
    });
};

// Fetch market prices
export const useMarketPrices = () => {
    return useQuery<any[]>({
        queryKey: ['market-prices'],
        queryFn: async () => {
            const { data } = await apiClient.get('/stats/market-prices');
            return data;
        },
        staleTime: 1000 * 60 * 60, // 1 hour
    });
};
