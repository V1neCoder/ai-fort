import { create } from 'zustand';

export interface PipelineJob {
    job_id: string;
    prompt: string;
    project: string;
    status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
    progress: number;
    progress_message: string;
    result?: any;
    error?: string;
    created_at: number;
    started_at?: number;
    completed_at?: number;
}

export interface AppState {
    // Cross-section navigation
    selectedAssetId: string | null;
    selectAsset: (id: string | null) => void;

    // Navigation intent (used to open asset in another section)
    navigationTarget: { section: string; assetId: string } | null;
    navigateTo: (section: string, assetId: string) => void;
    clearNavigation: () => void;

    // Pipeline jobs
    jobs: PipelineJob[];
    setJobs: (jobs: PipelineJob[]) => void;
    selectedJobId: string | null;
    selectJob: (id: string | null) => void;

    // Notifications
    notifications: { id: string; message: string; type: 'success' | 'error' | 'info' }[];
    addNotification: (message: string, type: 'success' | 'error' | 'info') => void;
    dismissNotification: (id: string) => void;
}

let notifCounter = 0;

const useAppStore = create<AppState>((set) => ({
    selectedAssetId: null,
    selectAsset: (id) => set({ selectedAssetId: id }),

    navigationTarget: null,
    navigateTo: (section, assetId) => set({
        navigationTarget: { section, assetId },
        selectedAssetId: assetId,
    }),
    clearNavigation: () => set({ navigationTarget: null }),

    jobs: [],
    setJobs: (jobs) => set({ jobs }),
    selectedJobId: null,
    selectJob: (id) => set({ selectedJobId: id }),

    notifications: [],
    addNotification: (message, type) => {
        const id = `notif-${++notifCounter}`;
        set((state) => ({
            notifications: [...state.notifications, { id, message, type }],
        }));
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            set((state) => ({
                notifications: state.notifications.filter((n) => n.id !== id),
            }));
        }, 5000);
    },
    dismissNotification: (id) =>
        set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
        })),
}));

export default useAppStore;
