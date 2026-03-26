import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
    Search, Filter, Grid, List, Box, Eye, Wand2, Upload,
    Tag, ChevronRight, RefreshCw, CheckCircle, XCircle, AlertTriangle, Trash2
} from 'lucide-react';
import useAppStore from '../../store/useAppStore';
import { useNavigate } from 'react-router-dom';
import '../../styles/Assets.css';

interface Props { backendUrl: string; }

interface AssetItem {
    asset_id: string;
    name: string;
    category: string;
    status: string;
    prompt: string;
    version: number;
    glb_path: string;
    vertex_count: number;
    face_count: number;
    preview_screenshots: string[];
    tags?: string[];
    updated_at: string;
    latest_validation?: any;
}

const STATUS_COLORS: Record<string, string> = {
    pending: '#888', generating: '#f0ad4e', approved: '#5cb85c',
    imported: '#337ab7', needs_correction: '#d9534f', preview_ready: '#5bc0de',
    build_failed: '#d9534f',
};

const CATEGORIES = ['all', 'furniture', 'architecture', 'terrain', 'prop', 'vegetation', 'vehicle'];

export default function AssetsView({ backendUrl }: Props) {
    const [assets, setAssets] = useState<AssetItem[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [categoryFilter, setCategoryFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('all');
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const { selectedAssetId, selectAsset, navigateTo } = useAppStore();
    const navigate = useNavigate();

    const fetchAssets = useCallback(async () => {
        try {
            const res = await axios.get(`${backendUrl}/api/pipeline/assets`);
            setAssets(res.data.assets || []);
        } catch { /* ignore */ }
    }, [backendUrl]);

    useEffect(() => {
        fetchAssets();
        const interval = setInterval(fetchAssets, 10000);
        return () => clearInterval(interval);
    }, [fetchAssets]);

    const filtered = assets.filter(a => {
        if (categoryFilter !== 'all' && a.category !== categoryFilter) return false;
        if (statusFilter !== 'all' && a.status !== statusFilter) return false;
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            return a.name.toLowerCase().includes(q) || a.prompt.toLowerCase().includes(q) || a.category.includes(q);
        }
        return true;
    });

    const selected = assets.find(a => a.asset_id === selectedAssetId);

    const glbUrl = (asset: AssetItem) => {
        if (!asset.glb_path) return '';
        const path = asset.glb_path.replace(/\\/g, '/');
        const idx = path.indexOf('ai_assets/');
        if (idx >= 0) return `${backendUrl}/ai_assets/${path.substring(idx + 'ai_assets/'.length)}`;
        return '';
    };

    const openInModelAI = (assetId: string) => {
        navigateTo('/model-ai', assetId);
        navigate('/model-ai');
    };

    const handleDelete = async (assetId: string) => {
        if (!window.confirm('Delete this asset? This cannot be undone.')) return;
        try {
            await axios.delete(`${backendUrl}/api/pipeline/delete/${assetId}`);
            if (selectedAssetId === assetId) selectAsset('');
            fetchAssets();
        } catch { /* ignore */ }
    };

    return (
        <div className="assets-v2">
            {/* Toolbar */}
            <div className="av2-toolbar">
                <div className="av2-search-group">
                    <Search size={16} />
                    <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Search assets..." className="av2-search" />
                </div>
                <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className="av2-filter">
                    {CATEGORIES.map(c => <option key={c} value={c}>{c === 'all' ? 'All Categories' : c}</option>)}
                </select>
                <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="av2-filter">
                    <option value="all">All Status</option>
                    <option value="approved">Approved</option>
                    <option value="imported">Imported</option>
                    <option value="preview_ready">Preview Ready</option>
                    <option value="needs_correction">Needs Fix</option>
                </select>
                <div className="av2-view-toggle">
                    <button className={viewMode === 'grid' ? 'active' : ''} onClick={() => setViewMode('grid')}><Grid size={16} /></button>
                    <button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')}><List size={16} /></button>
                </div>
                <button onClick={fetchAssets} className="av2-refresh"><RefreshCw size={16} /></button>
                <span className="av2-count">{filtered.length} assets</span>
            </div>

            <div className="av2-content">
                {/* Asset Grid/List */}
                <div className={`av2-grid ${viewMode}`}>
                    {filtered.length === 0 && (
                        <div className="av2-empty">
                            <Box size={32} />
                            <p>No assets found. Generate some from the Pipeline tab.</p>
                        </div>
                    )}
                    {filtered.map(asset => (
                        <div key={asset.asset_id}
                            className={`av2-card ${selectedAssetId === asset.asset_id ? 'selected' : ''}`}
                            onClick={() => selectAsset(asset.asset_id)}>
                            <div className="av2-card-thumb">
                                <Box size={24} />
                            </div>
                            <div className="av2-card-info">
                                <span className="av2-card-name">{asset.name}</span>
                                <div className="av2-card-meta">
                                    <span className="av2-cat-tag">{asset.category}</span>
                                    <span className="av2-badge" style={{ backgroundColor: STATUS_COLORS[asset.status] || '#888' }}>
                                        {asset.status}
                                    </span>
                                </div>
                                {viewMode === 'list' && <span className="av2-card-prompt">{asset.prompt}</span>}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Detail Panel */}
                {selected && (
                    <div className="av2-detail">
                        <h2>{selected.name}</h2>
                        <span className="av2-badge large" style={{ backgroundColor: STATUS_COLORS[selected.status] }}>{selected.status}</span>

                        {glbUrl(selected) && (
                            <div className="av2-preview">
                                {/* @ts-ignore */}
                                <model-viewer
                                    src={glbUrl(selected)} alt={selected.name}
                                    auto-rotate camera-controls shadow-intensity="1"
                                    style={{ width: '100%', height: '300px', backgroundColor: '#1a1a2e' }}
                                />
                            </div>
                        )}

                        <div className="av2-info">
                            <div className="av2-row"><span>Category:</span><span>{selected.category}</span></div>
                            <div className="av2-row"><span>Version:</span><span>v{selected.version}</span></div>
                            <div className="av2-row"><span>Vertices:</span><span>{selected.vertex_count?.toLocaleString()}</span></div>
                            <div className="av2-row"><span>Prompt:</span><span>{selected.prompt}</span></div>
                        </div>

                        {selected.latest_validation && (
                            <div className="av2-validation">
                                <div className="av2-score-bar">
                                    <div className="av2-score-fill" style={{
                                        width: `${(selected.latest_validation.overall_score || 0) * 100}%`,
                                        backgroundColor: selected.latest_validation.passed ? '#5cb85c' : '#d9534f'
                                    }} />
                                </div>
                                <span>{Math.round((selected.latest_validation.overall_score || 0) * 100)}%</span>
                            </div>
                        )}

                        <div className="av2-actions">
                            <button className="av2-action model-ai" onClick={() => openInModelAI(selected.asset_id)}>
                                <Eye size={16} /> Open in Model AI
                            </button>
                            <button className="av2-action pipeline" onClick={() => { navigateTo('/pipeline', selected.asset_id); navigate('/pipeline'); }}>
                                <Wand2 size={16} /> Send to Pipeline
                            </button>
                            <button className="av2-action delete" onClick={() => handleDelete(selected.asset_id)}>
                                <Trash2 size={16} /> Delete
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
