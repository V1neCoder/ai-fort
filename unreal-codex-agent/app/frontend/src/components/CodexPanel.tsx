import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Upload,
    Trash2,
    CheckCircle,
    AlertCircle,
    BookOpen,
    Brain,
    FileText,
    Zap,
    Library,
    Image as ImageIcon,
    Link2,
    Globe2,
    X,
    EyeOff,
    Search
} from 'lucide-react';
import axios from 'axios';
import '../styles/CodexPanel.css';

interface KnowledgeItem {
    id: string;
    type: 'file' | 'url' | 'text' | 'image';
    title: string;
    content: string;
    addedAt: string;
    /** 0 = excluded from AI context; default 1 */
    quality?: number;
    sourceUrl?: string;
}

interface PlanStep {
    step: number;
    title: string;
    description: string;
    tools: string[];
    status: 'pending' | 'in-progress' | 'completed';
}

interface DiscoverCandidate {
    title: string;
    url: string;
    snippet: string;
    source: string;
}

const LEGACY_KB_KEYS = ['codex_knowledge_base_v2', 'codex_knowledge_base'];
const BACKEND_MIGRATED_KEY = 'codex_knowledge_backend_migrated_v1';

function kbIcon(item: KnowledgeItem) {
    switch (item.type) {
        case 'image':
            return <ImageIcon size={18} className="kb-icon-svg" aria-hidden />;
        case 'url':
            return <Link2 size={18} className="kb-icon-svg" aria-hidden />;
        case 'text':
            return <FileText size={18} className="kb-icon-svg" aria-hidden />;
        default:
            return <FileText size={18} className="kb-icon-svg" aria-hidden />;
    }
}

function CodexPanel({ backendUrl }: { backendUrl: string }) {
    const [tab, setTab] = useState<'plan' | 'research'>('plan');
    const [planPrompt, setPlanPrompt] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [planSteps, setPlanSteps] = useState<PlanStep[]>([]);
    const [selectedStep, setSelectedStep] = useState<number | null>(null);

    const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeItem[]>([]);
    const [researchQuery, setResearchQuery] = useState('');
    const [isResearching, setIsResearching] = useState(false);
    const [researchResults, setResearchResults] = useState<any>(null);
    const [discovering, setDiscovering] = useState(false);
    const [discoverCandidates, setDiscoverCandidates] = useState<DiscoverCandidate[]>([]);
    const [previewItem, setPreviewItem] = useState<KnowledgeItem | null>(null);

    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const dropRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const loadKnowledgeBase = useCallback(async () => {
        try {
            const response = await axios.get(`${backendUrl}/api/knowledge`);
            const backendItems: KnowledgeItem[] = (response.data?.items || [])
                .filter((item: any) => item.source_type !== 'ai_saved')
                .map((item: any) => ({
                    ...item,
                    quality: item.quality ?? 1,
                }));

            if (backendItems.length === 0 && !localStorage.getItem(BACKEND_MIGRATED_KEY)) {
                let importedCount = 0;
                for (const key of LEGACY_KB_KEYS) {
                    const raw = localStorage.getItem(key);
                    if (!raw) continue;
                    try {
                        const parsed: KnowledgeItem[] = JSON.parse(raw);
                        for (const item of parsed) {
                            if (!item.title || !item.content) continue;
                            await axios.post(`${backendUrl}/api/knowledge`, {
                                type: item.type,
                                title: item.title,
                                content: item.content,
                                quality: item.quality ?? 1,
                                sourceUrl: item.sourceUrl || '',
                            });
                            importedCount += 1;
                        }
                    } catch (e) {
                        console.error('Legacy knowledge import failed:', e);
                    }
                }
                localStorage.setItem(BACKEND_MIGRATED_KEY, '1');
                const retryResponse = await axios.get(`${backendUrl}/api/knowledge`);
                setKnowledgeBase((retryResponse.data?.items || []).map((item: any) => ({
                    ...item,
                    quality: item.quality ?? 1,
                })));
                if (importedCount > 0) {
                    setSuccess(`Imported ${importedCount} saved knowledge item(s) into the shared backend store`);
                }
                return;
            }

            setKnowledgeBase(backendItems);
        } catch (e) {
            console.error('Failed to load backend knowledge base:', e);
            setError('Failed to load shared knowledge base.');
        }
    }, [backendUrl]);

    useEffect(() => {
        void loadKnowledgeBase();
    }, [loadKnowledgeBase]);

    function knowledgeContextSnippet(): string {
        return knowledgeBase
            .filter(k => k.quality !== 0)
            .map(k => `[${k.type.toUpperCase()}] ${k.title}: ${k.content.substring(0, 4000)}`)
            .join('\n---\n');
    }

    const addKnowledgeItem = useCallback(async (item: Omit<KnowledgeItem, 'id' | 'addedAt'>) => {
        try {
            const response = await axios.post(`${backendUrl}/api/knowledge`, {
                type: item.type,
                title: item.title,
                content: item.content,
                quality: item.quality ?? 1,
                sourceUrl: item.sourceUrl || '',
            });
            const created: KnowledgeItem = {
                ...response.data.item,
                quality: response.data.item?.quality ?? 1,
            };
            setKnowledgeBase(prev => [created, ...prev]);
            return created;
        } catch (error) {
            setError('Failed to save to the shared knowledge base.');
            throw error;
        }
    }, [backendUrl]);

    async function setItemQuality(id: string, quality: number) {
        try {
            const response = await axios.patch(`${backendUrl}/api/knowledge/${id}`, { quality });
            const updated: KnowledgeItem = {
                ...response.data.item,
                quality: response.data.item?.quality ?? quality,
            };
            setKnowledgeBase(prev => prev.map(k => (k.id === id ? updated : k)));
        } catch (error) {
            console.error('Failed to update knowledge quality:', error);
            setError('Failed to update knowledge item.');
        }
    }

    async function removeExcluded() {
        try {
            const excluded = knowledgeBase.filter(k => k.quality === 0);
            await Promise.all(excluded.map(item => axios.delete(`${backendUrl}/api/knowledge/${item.id}`)));
            setKnowledgeBase(prev => prev.filter(k => k.quality !== 0));
        } catch (error) {
            console.error('Failed to remove excluded knowledge:', error);
            setError('Failed to remove excluded knowledge items.');
        }
    }

    const ingestFile = useCallback((file: File) => {
        const isImage = file.type.startsWith('image/');
        const reader = new FileReader();
        reader.onload = async e => {
            const result = e.target?.result;
            const content = typeof result === 'string' ? result : '';
            try {
                await addKnowledgeItem({
                    type: isImage ? 'image' : 'file',
                    title: file.name,
                    content: isImage ? content : content.substring(0, 50000),
                    quality: 1
                });
                setSuccess(isImage ? `Image “${file.name}” added` : `File “${file.name}” added`);
            } catch (error) {
                console.error('Failed to add knowledge item:', error);
                setError(`Failed to save ${file.name} to the shared knowledge base`);
            }
        };
        if (isImage) {
            reader.readAsDataURL(file);
        } else {
            reader.readAsText(file);
        }
    }, [addKnowledgeItem]);

    const onDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            Array.from(e.dataTransfer.files || []).forEach(f => ingestFile(f));
        },
        [ingestFile]
    );

    const onPasteZone = useCallback(
        (e: React.ClipboardEvent) => {
            const items = e.clipboardData?.items;
            if (!items) return;
            let handled = false;
            for (let i = 0; i < items.length; i++) {
                const it = items[i];
                if (it.kind === 'file') {
                    const f = it.getAsFile();
                    if (f) {
                        ingestFile(f);
                        handled = true;
                    }
                }
            }
            if (handled) {
                e.preventDefault();
                setSuccess('Pasted file added to knowledge base');
            }
        },
        [ingestFile]
    );

    async function generatePlan() {
        if (!planPrompt.trim()) {
            setError('Describe what you want to build');
            return;
        }

        setError('');
        setSuccess('');
        setIsGenerating(true);

        try {
            const response = await axios.post(`${backendUrl}/api/codex/plan`, {
                description: planPrompt,
                goals: '',
                constraints: '',
                knowledge_context: knowledgeContextSnippet()
            });

            const rawSteps = response.data.plan?.steps || [];
            const steps = rawSteps.map((step: any, idx: number) => ({
                step: idx + 1,
                title: step.title || step.description?.slice(0, 80) || `Step ${idx + 1}`,
                description:
                    typeof step.description === 'string'
                        ? step.description
                        : String(step.description ?? step ?? ''),
                tools: Array.isArray(step.tools) ? step.tools : step.suggested_tools || [],
                status: (step.status as PlanStep['status']) || 'pending'
            }));

            setPlanSteps(steps);
            setSelectedStep(steps.length ? 0 : null);
            const snap = response.data.plan?.uefn_editor_snapshot;
            setSuccess(
                snap
                    ? 'Plan generated (includes live UEFN level snapshot)'
                    : 'Plan generated (start UEFN MCP listener for live editor data)'
            );
        } catch (err: any) {
            console.error('Failed to generate plan:', err);
            setError('Failed to generate plan. Is the backend running?');
        } finally {
            setIsGenerating(false);
        }
    }

    function executeStep(stepIndex: number) {
        const updatedSteps = [...planSteps];
        const cur = updatedSteps[stepIndex].status;
        updatedSteps[stepIndex] = {
            ...updatedSteps[stepIndex],
            status: cur === 'pending' ? 'in-progress' : cur === 'in-progress' ? 'completed' : 'pending'
        };
        setPlanSteps(updatedSteps);
    }

    async function runWebDiscover() {
        const q = researchQuery.trim();
        if (!q) {
            setError('Enter a topic to discover');
            return;
        }
        setError('');
        setDiscovering(true);
        setDiscoverCandidates([]);
        try {
            const response = await axios.post(`${backendUrl}/api/research/discover`, { query: q });
            setDiscoverCandidates(response.data.candidates || []);
            setSuccess(`Found ${(response.data.candidates || []).length} candidate links`);
        } catch (e: any) {
            setError(e?.response?.data?.error || 'Discovery failed');
        } finally {
            setDiscovering(false);
        }
    }

    async function keepCandidate(c: DiscoverCandidate) {
        try {
            await addKnowledgeItem({
                type: 'url',
                title: c.title.slice(0, 200),
                content: c.snippet || `Source: ${c.url}`,
                sourceUrl: c.url,
                quality: 1
            });
            setSuccess(`Kept: ${c.title.slice(0, 60)}…`);
        } catch {
            // addKnowledgeItem sets the error state
        }
    }

    async function performResearch() {
        if (!researchQuery.trim()) {
            setError('Enter a question');
            return;
        }

        setError('');
        setIsResearching(true);
        setResearchResults(null);

        try {
            const response = await axios.post(`${backendUrl}/api/research`, {
                query: researchQuery,
                knowledge_base: knowledgeBase.filter(k => k.quality !== 0),
                context: 'UEFN island design and development'
            });

            setResearchResults({
                query: researchQuery,
                findings: response.data.findings || [],
                recommendations: response.data.recommendations || [],
                sources_used: response.data.sources_used ?? knowledgeBase.filter(k => k.quality !== 0).length,
                timestamp: response.data.timestamp || new Date().toLocaleString()
            });
            setSuccess('Research finished');
        } catch (err: any) {
            console.error('Research failed:', err);
            setError('Research request failed. Check the backend.');
        } finally {
            setIsResearching(false);
        }
    }

    async function removeKnowledgeItem(id: string) {
        try {
            await axios.delete(`${backendUrl}/api/knowledge/${id}`);
            setKnowledgeBase(prev => prev.filter(item => item.id !== id));
        } catch (error) {
            console.error('Failed to remove knowledge item:', error);
            setError('Failed to remove knowledge item.');
        }
    }

    const activeKb = knowledgeBase.filter(k => k.quality !== 0);
    const excludedCount = knowledgeBase.length - activeKb.length;

    return (
        <div className="codex-panel-v2">
            {previewItem && (
                <div
                    className="kb-preview-overlay"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="kb-preview-title"
                >
                    <div className="kb-preview-card">
                        <div className="kb-preview-head">
                            <h3 id="kb-preview-title">{previewItem.title}</h3>
                            <button
                                type="button"
                                className="kb-preview-close"
                                onClick={() => setPreviewItem(null)}
                                aria-label="Close preview"
                            >
                                <X size={20} />
                            </button>
                        </div>
                        <p className="kb-preview-meta">
                            {previewItem.type}
                            {previewItem.sourceUrl && (
                                <>
                                    {' · '}
                                    <a href={previewItem.sourceUrl} target="_blank" rel="noreferrer">
                                        {previewItem.sourceUrl}
                                    </a>
                                </>
                            )}
                        </p>
                        <div className="kb-preview-body">
                            {previewItem.type === 'image' && previewItem.content.startsWith('data:image') ? (
                                <img src={previewItem.content} alt="" className="kb-preview-img" />
                            ) : (
                                <pre className="kb-preview-text">{previewItem.content}</pre>
                            )}
                        </div>
                        <div className="kb-preview-actions">
                                <button
                                    type="button"
                                    className="kb-exclude-btn"
                                    onClick={() => {
                                        void setItemQuality(previewItem.id, 0);
                                        setPreviewItem(null);
                                        setSuccess('Item excluded from AI context (still in list until you remove excluded)');
                                    }}
                                >
                                <EyeOff size={16} />
                                Exclude from AI
                            </button>
                            <button type="button" className="kb-preview-done" onClick={() => setPreviewItem(null)}>
                                Done
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="codex-top">
                <div className="codex-title-row">
                    <Brain size={28} className="codex-icon" />
                    <div>
                        <h2>Codex AI Studio</h2>
                        <p>
                            Knowledge base feeds plans and research. Exclude weak sources so later runs ignore them—remove
                            excluded entries when you are ready.
                        </p>
                    </div>
                </div>
                <div className="codex-tabs">
                    <button
                        type="button"
                        className={`tab-button ${tab === 'plan' ? 'active' : ''}`}
                        onClick={() => setTab('plan')}
                    >
                        <Zap size={18} />
                        Generate plan
                    </button>
                    <button
                        type="button"
                        className={`tab-button ${tab === 'research' ? 'active' : ''}`}
                        onClick={() => setTab('research')}
                    >
                        <BookOpen size={18} />
                        Research
                    </button>
                </div>
            </div>

            {error && (
                <div className="alert alert-error">
                    <AlertCircle size={18} />
                    <span>{error}</span>
                    <button type="button" className="alert-close" onClick={() => setError('')} aria-label="Dismiss">
                        ×
                    </button>
                </div>
            )}
            {success && (
                <div className="alert alert-success">
                    <CheckCircle size={18} />
                    <span>{success}</span>
                    <button type="button" className="alert-close" onClick={() => setSuccess('')} aria-label="Dismiss">
                        ×
                    </button>
                </div>
            )}

            <div className="codex-body-grid">
                <section className="kb-panel" aria-label="Knowledge base">
                    <div className="kb-heading">
                        <Library size={20} />
                        <div>
                            <h3>Knowledge base</h3>
                            <p>
                                Active for AI: {activeKb.length} item(s)
                                {excludedCount > 0 ? ` · ${excludedCount} excluded` : ''}
                            </p>
                        </div>
                    </div>

                    {excludedCount > 0 && (
                        <button type="button" className="kb-prune-btn" onClick={() => void removeExcluded()}>
                            Remove excluded entries from list
                        </button>
                    )}



                    <ul className="kb-list">
                        {knowledgeBase.length === 0 ? (
                            <li className="kb-empty">
                                <FileText size={28} />
                                <span>No items yet—add references your AI should remember.</span>
                            </li>
                        ) : (
                            knowledgeBase.map(item => (
                                <li
                                    key={item.id}
                                    className={`kb-item ${item.quality === 0 ? 'kb-item-excluded' : ''}`}
                                >
                                    <button
                                        type="button"
                                        className="kb-item-main-btn"
                                        onClick={() => setPreviewItem(item)}
                                    >
                                        <span className="kb-icon-wrap">{kbIcon(item)}</span>
                                        <div className="kb-item-text">
                                            <span className="kb-item-title">{item.title}</span>
                                            {item.quality === 0 && (
                                                <span className="kb-excluded-badge">Excluded</span>
                                            )}
                                            <p className="kb-snippet">
                                                {item.type === 'image'
                                                    ? `Image file (${item.content.startsWith('data:')
                                                        ? item.content.substring(item.content.indexOf('/') + 1, item.content.indexOf(';'))
                                                        : 'unknown format'})`
                                                    : item.content.startsWith('data:')
                                                        ? 'Binary file data'
                                                        : item.content.length > 120
                                                            ? `${item.content.slice(0, 120)}...`
                                                            : item.content}
                                            </p>
                                            <span className="kb-meta">{item.addedAt}</span>
                                        </div>
                                    </button>
                                    <button
                                        type="button"
                                        className="kb-remove"
                                        onClick={() => void removeKnowledgeItem(item.id)}
                                        aria-label={`Remove ${item.title}`}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </li>
                            ))
                        )}
                    </ul>
                </section>

                <section className="workspace-panel">
                    {tab === 'plan' && (
                        <div className="workspace-plan">
                            <label className="plan-label" htmlFor="plan-prompt">
                                What do you want to build?
                            </label>

                            {/* Quick file attach for plan context */}
                            <div className="plan-attach-row">
                                <button
                                    type="button"
                                    className="plan-attach-btn"
                                    onClick={() => fileInputRef.current?.click()}
                                    title="Attach a reference file for this plan"
                                >
                                    <Upload size={14} />
                                    Attach reference
                                </button>
                                <span className="plan-attach-hint">
                                    Quick-attach files for this plan, or manage your full library in the Research tab.
                                </span>
                            </div>

                            {/* Compact KB selector — toggle which items feed into generation */}
                            {knowledgeBase.length > 0 && (
                                <div className="plan-kb-selector">
                                    <span className="plan-kb-label">
                                        <Library size={14} />
                                        Knowledge base ({activeKb.length}/{knowledgeBase.length}):
                                    </span>
                                    <div className="plan-kb-chips">
                                        {knowledgeBase.map(item => (
                                            <button
                                                key={item.id}
                                                type="button"
                                                className={`plan-kb-chip ${item.quality === 0 ? 'excluded' : 'active'}`}
                                                onClick={() => void setItemQuality(item.id, item.quality === 0 ? 1 : 0)}
                                                title={item.quality === 0 ? 'Click to include' : 'Click to exclude'}
                                            >
                                                {kbIcon(item)}
                                                <span>{item.title.length > 24 ? item.title.slice(0, 22) + '...' : item.title}</span>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <textarea
                                id="plan-prompt"
                                className="plan-textarea-v2"
                                placeholder="Example: A 4-player parkour race with checkpoints..."
                                value={planPrompt}
                                onChange={e => setPlanPrompt(e.target.value)}
                                rows={10}
                            />

                            <button
                                type="button"
                                className={`plan-submit ${isGenerating ? 'loading' : ''}`}
                                onClick={generatePlan}
                                disabled={isGenerating}
                            >
                                {isGenerating ? 'Generating…' : (
                                    <>
                                        <Zap size={18} />
                                        Generate plan with Codex
                                    </>
                                )}
                            </button>

                            {planSteps.length > 0 && (
                                <div className="plan-output">
                                    <h4>Plan ({planSteps.length} steps)</h4>
                                    <div className="steps-list-v2">
                                        {planSteps.map((step, idx) => (
                                            <button
                                                type="button"
                                                key={idx}
                                                className={`step-row ${selectedStep === idx ? 'active' : ''}`}
                                                onClick={() => setSelectedStep(idx)}
                                            >
                                                <span className="step-num">{step.step}</span>
                                                <div className="step-text">
                                                    <div className="step-title">{step.title}</div>
                                                    <div className="step-sub">
                                                        {step.description && step.description.length > 120
                                                            ? `${step.description.slice(0, 120)}…`
                                                            : step.description}
                                                    </div>
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                    {selectedStep !== null && planSteps[selectedStep] && (
                                        <div className="step-detail-v2">
                                            <h5>{planSteps[selectedStep].title}</h5>
                                            <p>{planSteps[selectedStep].description}</p>
                                            {planSteps[selectedStep].tools?.length > 0 && (
                                                <div className="step-tools-v2">
                                                    {planSteps[selectedStep].tools.map((t, i) => (
                                                        <span key={i}>{t}</span>
                                                    ))}
                                                </div>
                                            )}
                                            <button
                                                type="button"
                                                className="step-advance"
                                                onClick={() => executeStep(selectedStep)}
                                            >
                                                Update step status
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {tab === 'research' && (
                        <div className="workspace-research">
                            {/* ── File Upload Zone (moved from sidebar) ── */}
                            <div
                                ref={dropRef}
                                className="kb-dropzone"
                                onDragOver={e => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                }}
                                onDrop={onDrop}
                                onPaste={onPasteZone}
                                tabIndex={0}
                                role="region"
                                aria-label="Drop files or paste from clipboard"
                            >
                                <Upload size={22} />
                                <p>
                                    <strong>Drop files</strong> here, click to browse, or <strong>paste</strong> while focused.
                                </p>
                                <button type="button" className="kb-browse" onClick={() => fileInputRef.current?.click()}>
                                    Choose files
                                </button>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    multiple
                                    accept="image/*,.txt,.md,.json,.pdf,.verse,.uasset"
                                    className="kb-file-input"
                                    onChange={ev => {
                                        const files = ev.target.files;
                                        if (files) {
                                            Array.from(files).forEach(ingestFile);
                                            ev.target.value = '';
                                        }
                                    }}
                                />
                            </div>

                            <label className="plan-label" htmlFor="research-q">
                                Research topic or question
                            </label>
                            <p className="research-hint">
                                Run <strong>Discover</strong> to pull candidate pages (DuckDuckGo), keep the good ones
                                into the knowledge base, then run <strong>Research</strong> to synthesize against your
                                stored sources.
                            </p>
                            <textarea
                                id="research-q"
                                className="research-textarea-v2"
                                placeholder="e.g. UEFN best practices for competitive islands…"
                                value={researchQuery}
                                onChange={e => setResearchQuery(e.target.value)}
                                rows={4}
                            />

                            <div className="discover-row">
                                <button
                                    type="button"
                                    className="discover-btn"
                                    onClick={runWebDiscover}
                                    disabled={discovering}
                                >
                                    <Globe2 size={18} />
                                    {discovering ? 'Discovering…' : 'Discover on the web'}
                                </button>
                                <button type="button" className="research-submit-inline" onClick={performResearch} disabled={isResearching}>
                                    <Search size={18} />
                                    {isResearching ? 'Working…' : 'Run research'}
                                </button>
                            </div>

                            {discoverCandidates.length > 0 && (
                                <div className="discover-results">
                                    <h4>Candidate links</h4>
                                    <p className="discover-sub">Keep sources you trust; skip the rest.</p>
                                    <ul className="discover-list">
                                        {discoverCandidates.map((c, i) => (
                                            <li key={`${c.url}-${i}`} className="discover-item">
                                                <div className="discover-text">
                                                    <a href={c.url} target="_blank" rel="noreferrer">
                                                        {c.title}
                                                    </a>
                                                    <span className="discover-url">{c.url}</span>
                                                </div>
                                                <button type="button" className="keep-btn" onClick={() => void keepCandidate(c)}>
                                                    Keep
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {researchResults && (
                                <div className="research-output">
                                    <div className="research-output-head">
                                        <h4>Findings</h4>
                                        <span className="ts">{researchResults.timestamp}</span>
                                    </div>
                                    <ul className="findings-ul">
                                        {(researchResults.findings || []).map((f: string, i: number) => (
                                            <li key={i}>{f}</li>
                                        ))}
                                    </ul>
                                    {(researchResults.recommendations || []).length > 0 && (
                                        <>
                                            <h5 className="rec-title">Recommendations</h5>
                                            <ul className="rec-ul">
                                                {researchResults.recommendations.map((r: string, i: number) => (
                                                    <li key={i}>{r}</li>
                                                ))}
                                            </ul>
                                        </>
                                    )}
                                    <p className="sources-line">
                                        Active knowledge items used: {researchResults.sources_used}
                                    </p>
                                </div>
                            )}
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}

export default CodexPanel;
