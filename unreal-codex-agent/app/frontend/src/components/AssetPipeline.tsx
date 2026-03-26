import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
    Wand2, RefreshCw, CheckCircle, XCircle, Upload, Trash2,
    ChevronRight, Loader, AlertTriangle, Eye, Box
} from 'lucide-react';
import './AssetPipeline.css';

interface PipelineProps {
    backendUrl: string;
}

interface PipelineAsset {
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
    latest_validation: any;
    updated_at: string;
}

const STATUS_COLORS: Record<string, string> = {
    pending: '#888',
    generating: '#f0ad4e',
    validating: '#5bc0de',
    preview_ready: '#5bc0de',
    approved: '#5cb85c',
    imported: '#337ab7',
    needs_correction: '#d9534f',
    build_failed: '#d9534f',
    generation_failed: '#d9534f',
};

const STATUS_LABELS: Record<string, string> = {
    pending: 'Pending',
    generating: 'Generating...',
    validating: 'Validating...',
    preview_ready: 'Preview Ready',
    approved: 'Approved',
    imported: 'Imported to UEFN',
    needs_correction: 'Needs Fix',
    build_failed: 'Build Failed',
    generation_failed: 'Gen Failed',
};

export default function AssetPipeline({ backendUrl }: PipelineProps) {
    const [prompt, setPrompt] = useState('');
    const [assets, setAssets] = useState<PipelineAsset[]>([]);
    const [selected, setSelected] = useState<PipelineAsset | null>(null);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState('');
    const [actionLoading, setActionLoading] = useState('');

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

    const handleGenerate = async () => {
        if (!prompt.trim() || generating) return;
        setGenerating(true);
        setError('');
        try {
            const res = await axios.post(`${backendUrl}/api/pipeline/generate`, {
                prompt: prompt.trim(),
                auto_approve: true,
            });
            if (res.data.error) {
                setError(res.data.error);
            } else {
                setPrompt('');
                await fetchAssets();
                // Select the newly created asset
                if (res.data.asset_id) {
                    const detail = await axios.get(`${backendUrl}/api/pipeline/asset/${res.data.asset_id}`);
                    setSelected(detail.data);
                }
            }
        } catch (e: any) {
            setError(e.response?.data?.error || e.message);
        } finally {
            setGenerating(false);
        }
    };

    const handleAction = async (action: string, assetId: string) => {
        setActionLoading(action);
        try {
            if (action === 'validate') {
                await axios.post(`${backendUrl}/api/pipeline/validate/${assetId}`);
            } else if (action === 'approve') {
                await axios.post(`${backendUrl}/api/pipeline/approve/${assetId}`);
            } else if (action === 'import') {
                await axios.post(`${backendUrl}/api/pipeline/import/${assetId}`);
            } else if (action === 'delete') {
                await axios.delete(`${backendUrl}/api/pipeline/delete/${assetId}`);
                setSelected(null);
            }
            await fetchAssets();
            if (action !== 'delete' && selected?.asset_id === assetId) {
                const detail = await axios.get(`${backendUrl}/api/pipeline/asset/${assetId}`);
                setSelected(detail.data);
            }
        } catch (e: any) {
            setError(e.response?.data?.error || e.message);
        } finally {
            setActionLoading('');
        }
    };

    const glbUrl = (asset: PipelineAsset) => {
        if (!asset.glb_path) return '';
        // Extract relative path after data/ai_assets/
        const idx = asset.glb_path.replace(/\\/g, '/').indexOf('ai_assets/');
        if (idx >= 0) {
            const rel = asset.glb_path.replace(/\\/g, '/').substring(idx + 'ai_assets/'.length);
            return `${backendUrl}/ai_assets/${rel}`;
        }
        return '';
    };

    return (
        <div className="pipeline-container">
            {/* Prompt Bar */}
            <div className="pipeline-prompt-bar">
                <div className="prompt-input-group">
                    <Wand2 size={20} className="prompt-icon" />
                    <input
                        type="text"
                        value={prompt}
                        onChange={e => setPrompt(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleGenerate()}
                        placeholder="Describe a 3D asset... (e.g., 'medieval wooden chair')"
                        disabled={generating}
                        className="prompt-input"
                    />
                    <button
                        onClick={handleGenerate}
                        disabled={generating || !prompt.trim()}
                        className="generate-btn"
                    >
                        {generating ? <Loader size={18} className="spin" /> : <Wand2 size={18} />}
                        {generating ? 'Generating...' : 'Generate'}
                    </button>
                </div>
                {error && (
                    <div className="pipeline-error">
                        <AlertTriangle size={14} /> {error}
                        <button onClick={() => setError('')} className="dismiss-btn">x</button>
                    </div>
                )}
            </div>

            <div className="pipeline-content">
                {/* Asset List */}
                <div className="pipeline-list">
                    <div className="list-header">
                        <h3>Pipeline Assets</h3>
                        <button onClick={fetchAssets} className="refresh-btn" title="Refresh">
                            <RefreshCw size={16} />
                        </button>
                    </div>

                    {assets.length === 0 && (
                        <div className="empty-state">
                            <Box size={32} />
                            <p>No assets yet. Enter a prompt above to generate one.</p>
                        </div>
                    )}

                    {assets.map(asset => (
                        <div
                            key={asset.asset_id}
                            className={`asset-card ${selected?.asset_id === asset.asset_id ? 'selected' : ''}`}
                            onClick={() => setSelected(asset)}
                        >
                            <div className="asset-card-header">
                                <span className="asset-name">{asset.name}</span>
                                <span
                                    className="status-badge"
                                    style={{ backgroundColor: STATUS_COLORS[asset.status] || '#888' }}
                                >
                                    {STATUS_LABELS[asset.status] || asset.status}
                                </span>
                            </div>
                            <div className="asset-card-meta">
                                <span className="category-tag">{asset.category}</span>
                                <span className="version-tag">v{asset.version}</span>
                                {asset.vertex_count > 0 && (
                                    <span className="vert-count">{asset.vertex_count.toLocaleString()} verts</span>
                                )}
                            </div>
                            <div className="asset-card-prompt">{asset.prompt}</div>
                            <ChevronRight size={16} className="card-arrow" />
                        </div>
                    ))}
                </div>

                {/* Detail Panel */}
                <div className="pipeline-detail">
                    {selected ? (
                        <>
                            <div className="detail-header">
                                <h2>{selected.name}</h2>
                                <span
                                    className="status-badge large"
                                    style={{ backgroundColor: STATUS_COLORS[selected.status] || '#888' }}
                                >
                                    {STATUS_LABELS[selected.status] || selected.status}
                                </span>
                            </div>

                            {/* 3D Preview */}
                            {selected.glb_path && glbUrl(selected) && (
                                <div className="model-preview">
                                    {/* @ts-ignore */}
                                    <model-viewer
                                        src={glbUrl(selected)}
                                        alt={selected.name}
                                        auto-rotate
                                        camera-controls
                                        shadow-intensity="1"
                                        style={{ width: '100%', height: '400px', backgroundColor: '#1a1a2e' }}
                                    />
                                </div>
                            )}

                            {/* Info */}
                            <div className="detail-info">
                                <div className="info-row">
                                    <span className="info-label">Category:</span>
                                    <span>{selected.category}</span>
                                </div>
                                <div className="info-row">
                                    <span className="info-label">Version:</span>
                                    <span>v{selected.version}</span>
                                </div>
                                <div className="info-row">
                                    <span className="info-label">Vertices:</span>
                                    <span>{selected.vertex_count?.toLocaleString() || 0}</span>
                                </div>
                                <div className="info-row">
                                    <span className="info-label">Faces:</span>
                                    <span>{selected.face_count?.toLocaleString() || 0}</span>
                                </div>
                                <div className="info-row">
                                    <span className="info-label">Prompt:</span>
                                    <span>{selected.prompt}</span>
                                </div>
                            </div>

                            {/* Validation */}
                            {selected.latest_validation && (
                                <div className="validation-section">
                                    <h3>Validation</h3>
                                    <div className="validation-score">
                                        <div className="score-bar">
                                            <div
                                                className="score-fill"
                                                style={{
                                                    width: `${(selected.latest_validation.overall_score || 0) * 100}%`,
                                                    backgroundColor: selected.latest_validation.passed ? '#5cb85c' : '#d9534f',
                                                }}
                                            />
                                        </div>
                                        <span className="score-text">
                                            {((selected.latest_validation.overall_score || 0) * 100).toFixed(0)}%
                                            {selected.latest_validation.passed ?
                                                <CheckCircle size={14} style={{ color: '#5cb85c', marginLeft: 4 }} /> :
                                                <XCircle size={14} style={{ color: '#d9534f', marginLeft: 4 }} />
                                            }
                                        </span>
                                    </div>
                                    {selected.latest_validation.issues?.length > 0 && (
                                        <div className="validation-issues">
                                            {selected.latest_validation.issues.map((issue: string, i: number) => (
                                                <div key={i} className="issue-item">
                                                    <AlertTriangle size={12} /> {issue}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Actions */}
                            <div className="detail-actions">
                                <button
                                    onClick={() => handleAction('validate', selected.asset_id)}
                                    disabled={!!actionLoading}
                                    className="action-btn validate"
                                >
                                    <Eye size={16} />
                                    {actionLoading === 'validate' ? 'Validating...' : 'Re-validate'}
                                </button>
                                {selected.status !== 'approved' && selected.status !== 'imported' && (
                                    <button
                                        onClick={() => handleAction('approve', selected.asset_id)}
                                        disabled={!!actionLoading}
                                        className="action-btn approve"
                                    >
                                        <CheckCircle size={16} />
                                        {actionLoading === 'approve' ? 'Approving...' : 'Approve'}
                                    </button>
                                )}
                                {(selected.status === 'approved') && (
                                    <button
                                        onClick={() => handleAction('import', selected.asset_id)}
                                        disabled={!!actionLoading}
                                        className="action-btn import"
                                    >
                                        <Upload size={16} />
                                        {actionLoading === 'import' ? 'Importing...' : 'Import to UEFN'}
                                    </button>
                                )}
                                <button
                                    onClick={() => handleAction('delete', selected.asset_id)}
                                    disabled={!!actionLoading}
                                    className="action-btn delete"
                                >
                                    <Trash2 size={16} />
                                    Delete
                                </button>
                            </div>
                        </>
                    ) : (
                        <div className="empty-detail">
                            <Box size={48} />
                            <p>Select an asset to view details</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
