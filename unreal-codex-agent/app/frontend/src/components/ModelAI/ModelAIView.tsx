import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Box, ArrowLeft, Loader } from 'lucide-react';
import useAppStore from '../../store/useAppStore';
import { useNavigate } from 'react-router-dom';
import ModelViewer3D, { ViewMode } from './ModelViewer3D';
import ViewerToolbar from './ViewerToolbar';
import MeshStats from './MeshStats';
import '../../styles/ModelAI.css';

interface Props { backendUrl: string; }

interface AssetData {
    asset_id: string;
    name: string;
    category: string;
    status: string;
    prompt: string;
    version: number;
    glb_path: string;
    vertex_count: number;
    face_count: number;
    bounds_cm?: any;
    latest_validation?: any;
    generated_code?: string;
}

export default function ModelAIView({ backendUrl }: Props) {
    const { selectedAssetId, selectAsset, navigationTarget, clearNavigation } = useAppStore();
    const [asset, setAsset] = useState<AssetData | null>(null);
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'edit' | 'references' | 'validation'>('edit');
    const [viewMode, setViewMode] = useState<ViewMode>('solid');
    const [autoRotate, setAutoRotate] = useState(true);
    const [screenshotTrigger, setScreenshotTrigger] = useState(0);
    const [meshStats, setMeshStats] = useState({ vertices: 0, triangles: 0, bounds: [0, 0, 0] });
    const [editPrompt, setEditPrompt] = useState('');
    const [editLoading, setEditLoading] = useState(false);
    const [editError, setEditError] = useState('');
    const navigate = useNavigate();

    // Handle navigation from other sections
    useEffect(() => {
        if (navigationTarget?.section === '/model-ai' && navigationTarget.assetId) {
            selectAsset(navigationTarget.assetId);
            clearNavigation();
        }
    }, [navigationTarget, selectAsset, clearNavigation]);

    // Fetch asset data
    const fetchAsset = useCallback(async () => {
        if (!selectedAssetId) { setAsset(null); return; }
        setLoading(true);
        try {
            const res = await axios.get(`${backendUrl}/api/pipeline/asset/${selectedAssetId}`);
            setAsset(res.data);
        } catch {
            setAsset(null);
        } finally {
            setLoading(false);
        }
    }, [backendUrl, selectedAssetId]);

    useEffect(() => { fetchAsset(); }, [fetchAsset]);

    const glbUrl = asset?.glb_path
        ? (() => {
            const path = asset.glb_path.replace(/\\/g, '/');
            const idx = path.indexOf('ai_assets/');
            return idx >= 0 ? `${backendUrl}/ai_assets/${path.substring(idx + 'ai_assets/'.length)}` : '';
        })()
        : '';

    const handleEdit = async () => {
        if (!editPrompt.trim() || !asset || editLoading) return;
        setEditLoading(true);
        setEditError('');
        try {
            const res = await axios.post(`${backendUrl}/api/model-ai/edit`, {
                asset_id: asset.asset_id,
                edit_prompt: editPrompt.trim(),
            });
            if (res.data.job_id) {
                // Poll for completion
                const poll = setInterval(async () => {
                    try {
                        const jr = await axios.get(`${backendUrl}/api/pipeline/jobs/${res.data.job_id}`);
                        if (jr.data.status === 'completed' || jr.data.status === 'failed') {
                            clearInterval(poll);
                            setEditLoading(false);
                            if (jr.data.status === 'completed') {
                                setEditPrompt('');
                                fetchAsset(); // Reload updated asset
                            } else {
                                setEditError(jr.data.error || 'Edit failed');
                            }
                        }
                    } catch { clearInterval(poll); setEditLoading(false); }
                }, 2000);
            }
        } catch (e: any) {
            setEditError(e.response?.data?.error || e.message);
            setEditLoading(false);
        }
    };

    const handleApprove = async () => {
        if (!asset) return;
        try {
            await axios.post(`${backendUrl}/api/pipeline/approve/${asset.asset_id}`);
            fetchAsset();
        } catch { /* ignore */ }
    };

    const handleImport = async () => {
        if (!asset) return;
        try {
            await axios.post(`${backendUrl}/api/pipeline/import/${asset.asset_id}`);
            fetchAsset();
        } catch { /* ignore */ }
    };

    if (loading) {
        return <div className="mai-loading"><Loader size={24} className="spin" /><span>Loading model...</span></div>;
    }

    if (!asset) {
        return (
            <div className="mai-empty">
                <Box size={48} />
                <h3>Model AI Workspace</h3>
                <p>Select an asset from Assets or Pipeline to inspect, edit, and fix it here.</p>
                <button className="mai-goto-btn" onClick={() => navigate('/assets')}>Browse Assets</button>
            </div>
        );
    }

    return (
        <div className="mai-container">
            {/* Top Bar */}
            <div className="mai-topbar">
                <button className="mai-back" onClick={() => navigate('/assets')}>
                    <ArrowLeft size={16} /> Assets
                </button>
                <h2>{asset.name}</h2>
                <span className="mai-cat-badge">{asset.category}</span>
                <span className="mai-status" style={{ backgroundColor: asset.status === 'approved' ? '#5cb85c' : asset.status === 'imported' ? '#337ab7' : '#888' }}>
                    {asset.status}
                </span>
            </div>

            <div className="mai-split">
                {/* Left: 3D Viewer */}
                <div className="mai-viewer-pane">
                    <ViewerToolbar
                        viewMode={viewMode}
                        onViewModeChange={setViewMode}
                        autoRotate={autoRotate}
                        onAutoRotateToggle={() => setAutoRotate(!autoRotate)}
                        onScreenshot={() => setScreenshotTrigger(t => t + 1)}
                        onCameraPreset={() => {}} // TODO: wire to camera ref
                    />
                    <div className="mai-canvas-wrap">
                        {glbUrl ? (
                            <ModelViewer3D
                                glbUrl={glbUrl}
                                viewMode={viewMode}
                                autoRotate={autoRotate}
                                onMeshStats={setMeshStats}
                                screenshotTrigger={screenshotTrigger}
                            />
                        ) : (
                            <div className="mai-no-model"><Box size={40} /><p>No 3D model available</p></div>
                        )}
                    </div>
                    <MeshStats
                        vertices={meshStats.vertices || asset.vertex_count || 0}
                        triangles={meshStats.triangles || asset.face_count || 0}
                        bounds={meshStats.bounds}
                        version={asset.version}
                    />
                </div>

                {/* Right: Tabs */}
                <div className="mai-panel">
                    <div className="mai-tabs">
                        {(['edit', 'references', 'validation'] as const).map(tab => (
                            <button key={tab}
                                className={`mai-tab ${activeTab === tab ? 'active' : ''}`}
                                onClick={() => setActiveTab(tab)}>
                                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                            </button>
                        ))}
                    </div>

                    <div className="mai-tab-content">
                        {activeTab === 'edit' && (
                            <div className="mai-edit-panel">
                                <p className="mai-prompt-label">Original: <em>{asset.prompt}</em></p>
                                <p className="mai-hint">Describe what to change about this model:</p>
                                <textarea
                                    className="mai-edit-input"
                                    placeholder='e.g., "Make the roof steeper", "Add windows", "Change color to blue"'
                                    rows={3}
                                    value={editPrompt}
                                    onChange={e => setEditPrompt(e.target.value)}
                                    disabled={editLoading}
                                />
                                <button className="mai-apply-btn" onClick={handleEdit} disabled={editLoading || !editPrompt.trim()}>
                                    {editLoading ? <><Loader size={14} className="spin" /> Editing...</> : 'Apply Edit'}
                                </button>
                                {editError && <div className="mai-edit-error">{editError}</div>}
                            </div>
                        )}
                        {activeTab === 'references' && (
                            <div className="mai-ref-panel">
                                <p className="mai-hint">Upload reference images to guide generation or edits.</p>
                                <div className="mai-dropzone">
                                    <Box size={24} />
                                    <p>Drag & drop images here</p>
                                </div>
                                <p className="mai-coming-soon">Reference analysis coming soon</p>
                            </div>
                        )}
                        {activeTab === 'validation' && (
                            <div className="mai-val-panel">
                                {asset.latest_validation ? (
                                    <>
                                        <div className="mai-score">
                                            <div className="mai-score-bar">
                                                <div className="mai-score-fill" style={{
                                                    width: `${(asset.latest_validation.overall_score || 0) * 100}%`,
                                                    backgroundColor: asset.latest_validation.passed ? '#5cb85c' : '#d9534f'
                                                }} />
                                            </div>
                                            <span>{Math.round((asset.latest_validation.overall_score || 0) * 100)}%</span>
                                        </div>
                                        {asset.latest_validation.issues?.map((issue: string, i: number) => (
                                            <div key={i} className="mai-issue">{issue}</div>
                                        ))}
                                        {asset.latest_validation.recommendations?.map((rec: string, i: number) => (
                                            <div key={i} className="mai-rec">{rec}</div>
                                        ))}
                                    </>
                                ) : (
                                    <p className="mai-hint">No validation results yet.</p>
                                )}

                                <div className="mai-val-actions">
                                    {asset.status !== 'approved' && asset.status !== 'imported' && (
                                        <button className="mai-approve-btn" onClick={handleApprove}>Approve</button>
                                    )}
                                    {asset.status === 'approved' && (
                                        <button className="mai-import-btn" onClick={handleImport}>Import to UEFN</button>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
