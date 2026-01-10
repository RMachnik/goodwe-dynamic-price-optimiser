import { useQuery } from '@tanstack/react-query';
import apiClient from './client';

export interface Node {
    id: string;
    hardware_id: string;
    name: string;
    is_online: boolean;
    last_seen: string;
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
