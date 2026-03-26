import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
    Wand2, Loader, AlertTriangle, RefreshCw, X as XIcon,
    ChevronRight, CheckCircle, XCircle, Eye, Upload, Trash2, Box, Play, Square
} from 'lucide-react';
import useAppStore, { PipelineJob } from '../../store/useAppStore';
import { useNavigate } from 'react-router-dom';
import '../../styles/Pipeline.css';

interface Props { backendUrl: string; }

const STATUS_COLORS: Record<string, string> = {
    queued: '#888', running: '#f0ad4e', completed: '#5cb85c',
    failed: '#d9534f', cancelled: '#777',
};

export default function PipelineView({ backendUrl }: Props) {
    const [prompt, setPrompt] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const { jobs, setJobs, selectedJobId, selectJob, navigateTo } = useAppStore();
    const navigate = useNavigate();

    const fetchJobs = useCallback(async () => {
        try {
            const res = await axios.get(`${backendUrl}/api/pipeline/jobs`);
            setJobs(res.data.jobs || []);
        } catch { /* ignore */ }
    }, [backendUrl, setJobs]);

    useEffect(() => {
        fetchJobs();
        const interval = setInterval(fetchJobs, 2000);
        return () => clearInterval(interval);
    }, [fetchJobs]);

    const handleGenerate = async () => {
        if (!prompt.trim() || submitting) return;
        setSubmitting(true);
        setError('');
        try {
            const res = await axios.post(`${backendUrl}/api/pipeline/generate`, {
                prompt: prompt.trim(), auto_approve: true,
            });
            if (res.data.job_id) {
                selectJob(res.data.job_id);
                setPrompt('');
            }
        } catch (e: any) {
            setError(e.response?.data?.error || e.message);
        } finally {
            setSubmitting(false);
        }
    };

    const handleCancel = async (jobId: string) => {
        try {
            await axios.post(`${backendUrl}/api/pipeline/jobs/${jobId}/cancel`);
            fetchJobs();
        } catch { /* ignore */ }
    };

    const selectedJob = jobs.find(j => j.job_id === selectedJobId);

    const openInModelAI = (assetId: string) => {
        navigateTo('/model-ai', assetId);
        navigate('/model-ai');
    };

    const handleDeleteAsset = async (assetId: string) => {
        if (!window.confirm('Delete this asset and all its files?')) return;
        try {
            await axios.delete(`${backendUrl}/api/pipeline/delete/${assetId}`);
            fetchJobs();
        } catch { /* ignore */ }
    };

    const glbUrl = (result: any) => {
        if (!result?.glb_path) return '';
        const path = result.glb_path.replace(/\\/g, '/');
        const idx = path.indexOf('ai_assets/');
        if (idx >= 0) return `${backendUrl}/ai_assets/${path.substring(idx + 'ai_assets/'.length)}`;
        return '';
    };

    return (
        <div className="pipeline-v2">
            {/* Prompt Bar */}
            <div className="pv2-prompt-bar">
                <div className="pv2-prompt-group">
                    <Wand2 size={20} className="pv2-prompt-icon" />
                    <input
                        type="text" value={prompt}
                        onChange={e => setPrompt(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleGenerate()}
                        placeholder="Describe a 3D asset to generate..."
                        disabled={submitting} className="pv2-prompt-input"
                    />
                    <button onClick={handleGenerate} disabled={submitting || !prompt.trim()} className="pv2-gen-btn">
                        {submitting ? <Loader size={16} className="spin" /> : <Play size={16} />}
                        {submitting ? 'Starting...' : 'Generate'}
                    </button>
                </div>
                {error && (
                    <div className="pv2-error">
                        <AlertTriangle size={14} /> {error}
                        <button onClick={() => setError('')} className="pv2-dismiss">x</button>
                    </div>
                )}
            </div>

            <div className="pv2-content">
                {/* Job List */}
                <div className="pv2-job-list">
                    <div className="pv2-list-header">
                        <h3>Jobs</h3>
                        <button onClick={fetchJobs} className="pv2-refresh"><RefreshCw size={14} /></button>
                    </div>
                    {jobs.length === 0 && (
                        <div className="pv2-empty"><Box size={28} /><p>No jobs yet</p></div>
                    )}
                    {jobs.map(job => (
                        <div key={job.job_id}
                            className={`pv2-job-card ${selectedJobId === job.job_id ? 'selected' : ''}`}
                            onClick={() => selectJob(job.job_id)}>
                            <div className="pv2-job-top">
                                <span className="pv2-job-prompt">{job.prompt}</span>
                                <span className="pv2-badge" style={{ backgroundColor: STATUS_COLORS[job.status] || '#888' }}>
                                    {job.status}
                                </span>
                            </div>
                            {job.status === 'running' && (
                                <div className="pv2-progress-wrap">
                                    <div className="pv2-progress-bar">
                                        <div className="pv2-progress-fill" style={{ width: `${job.progress * 100}%` }} />
                                    </div>
                                    <span className="pv2-progress-msg">{job.progress_message}</span>
                                </div>
                            )}
                            {job.status === 'running' && (
                                <button className="pv2-cancel-btn" onClick={e => { e.stopPropagation(); handleCancel(job.job_id); }}>
                                    <Square size={12} /> Cancel
                                </button>
                            )}
                            <ChevronRight size={14} className="pv2-arrow" />
                        </div>
                    ))}
                </div>

                {/* Job Detail */}
                <div className="pv2-detail">
                    {selectedJob ? (
                        <>
                            <h2>{selectedJob.prompt}</h2>
                            <div className="pv2-detail-meta">
                                <span className="pv2-badge large" style={{ backgroundColor: STATUS_COLORS[selectedJob.status] }}>
                                    {selectedJob.status}
                                </span>
                                {selectedJob.status === 'running' && (
                                    <span className="pv2-progress-msg">{selectedJob.progress_message} ({Math.round(selectedJob.progress * 100)}%)</span>
                                )}
                            </div>

                            {selectedJob.status === 'running' && (
                                <div className="pv2-progress-wrap large">
                                    <div className="pv2-progress-bar large">
                                        <div className="pv2-progress-fill" style={{ width: `${selectedJob.progress * 100}%` }} />
                                    </div>
                                </div>
                            )}

                            {selectedJob.result && glbUrl(selectedJob.result) && (
                                <div className="pv2-model-preview">
                                    {/* @ts-ignore */}
                                    <model-viewer
                                        src={glbUrl(selectedJob.result)}
                                        alt={selectedJob.prompt}
                                        auto-rotate camera-controls shadow-intensity="1"
                                        style={{ width: '100%', height: '350px', backgroundColor: '#1a1a2e' }}
                                    />
                                </div>
                            )}

                            {selectedJob.result && (
                                <div className="pv2-result-info">
                                    <div className="pv2-info-row"><span>Status:</span><span>{selectedJob.result.status}</span></div>
                                    <div className="pv2-info-row"><span>Vertices:</span><span>{selectedJob.result.vertex_count?.toLocaleString()}</span></div>
                                    <div className="pv2-info-row"><span>Faces:</span><span>{selectedJob.result.face_count?.toLocaleString()}</span></div>
                                    {selectedJob.result.validation?.overall_score != null && (
                                        <div className="pv2-info-row">
                                            <span>Validation:</span>
                                            <span>{Math.round(selectedJob.result.validation.overall_score * 100)}%
                                                {selectedJob.result.validation.passed
                                                    ? <CheckCircle size={14} style={{ color: '#5cb85c', marginLeft: 4 }} />
                                                    : <XCircle size={14} style={{ color: '#d9534f', marginLeft: 4 }} />}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            )}

                            {selectedJob.error && (
                                <div className="pv2-error-box">
                                    <AlertTriangle size={14} /> {selectedJob.error}
                                </div>
                            )}

                            {selectedJob.result?.asset_id && (
                                <div className="pv2-actions">
                                    <button className="pv2-action-btn model-ai" onClick={() => openInModelAI(selectedJob.result.asset_id)}>
                                        <Eye size={16} /> Open in Model AI
                                    </button>
                                    <button className="pv2-action-btn assets" onClick={() => { navigateTo('/assets', selectedJob.result.asset_id); navigate('/assets'); }}>
                                        <Box size={16} /> View in Assets
                                    </button>
                                    <button className="pv2-action-btn danger" onClick={() => handleDeleteAsset(selectedJob.result.asset_id)}>
                                        <Trash2 size={16} /> Delete Asset
                                    </button>
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="pv2-empty-detail">
                            <Wand2 size={40} />
                            <p>Enter a prompt to generate a 3D asset, or select a job to view details.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
