import React, { useState, useEffect, useCallback } from 'react';
import { Save, RefreshCw, Plug, Terminal, Sparkles, CheckCircle, AlertCircle, Key, Zap, Eye, EyeOff } from 'lucide-react';
import axios from 'axios';
import '../styles/SettingsPanel.css';

interface ProviderInfo {
    label: string;
    hint: string;
    has_key: boolean;
    models: string[];
    default_model: string;
}

// Static provider definitions so UI renders instantly before backend responds
const STATIC_PROVIDERS: Record<string, { label: string; hint: string; key_env: string; models: string[]; default_model: string }> = {
    groq: {
        label: 'Groq (free, fastest)',
        hint: 'Get free key at console.groq.com — 14,400 requests/day',
        key_env: 'GROQ_API_KEY',
        models: ['llama-3.3-70b-versatile', 'deepseek-r1-distill-llama-70b', 'llama-3.1-8b-instant', 'gemma2-9b-it'],
        default_model: 'llama-3.3-70b-versatile',
    },
    cerebras: {
        label: 'Cerebras (free, ultra-fast)',
        hint: 'Get free key at cloud.cerebras.ai — 1M tokens/day',
        key_env: 'CEREBRAS_API_KEY',
        models: ['qwen-3-235b-a22b-instruct-2507', 'llama3.1-8b'],
        default_model: 'qwen-3-235b-a22b-instruct-2507',
    },
    gemini: {
        label: 'Google Gemini (free, smartest)',
        hint: 'Get free key at aistudio.google.dev — 1M token context',
        key_env: 'GEMINI_API_KEY',
        models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
        default_model: 'gemini-2.5-flash',
    },
    ollama: {
        label: 'Ollama (local, unlimited)',
        hint: 'Install from ollama.com, then: ollama pull llama3.1',
        key_env: '',
        models: [],
        default_model: 'llama3.1',
    },
};

// ── LocalStorage cache helpers ──────────────────────────────────────────
const CACHE_KEY_AI = '_codex_ai_status';
const CACHE_KEY_MCP = '_codex_mcp_status';

function cacheRead(key: string): any {
    try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : null; } catch { return null; }
}
function cacheWrite(key: string, data: any) {
    try { localStorage.setItem(key, JSON.stringify(data)); } catch { /* quota */ }
}

function SettingsPanel({ appInfo, backendUrl }: any) {
    // ── Restore from cache instantly on mount ──
    const cachedAi = cacheRead(CACHE_KEY_AI);
    const cachedMcp = cacheRead(CACHE_KEY_MCP);

    const [config, setConfig] = useState<any>({});
    const [mcp, setMcp] = useState<any>(cachedMcp);
    const [mcpTest, setMcpTest] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [saved, setSaved] = useState(false);

    // AI Chat settings — pre-populate from cache so nothing flickers
    const [aiStatus, setAiStatus] = useState<any>(cachedAi);
    const [activeProvider, setActiveProvider] = useState(cachedAi?.provider || '');
    const [activeModel, setActiveModel] = useState(cachedAi?.model || '');
    const [selectedProvider, setSelectedProvider] = useState(cachedAi?.provider || 'groq');
    const [selectedModel, setSelectedModel] = useState(cachedAi?.model || 'llama-3.3-70b-versatile');
    const [providerModels, setProviderModels] = useState<Record<string, string>>(cachedAi?.provider_models || {});

    // Per-provider key inputs
    const [keyInputs, setKeyInputs] = useState<Record<string, string>>({ groq: '', cerebras: '', gemini: '' });
    const [keyVisible, setKeyVisible] = useState<Record<string, boolean>>({});
    const [savingAi, setSavingAi] = useState(false);
    const [aiSaved, setAiSaved] = useState<string>('');
    const [backendProviders, setBackendProviders] = useState<Record<string, ProviderInfo>>(cachedAi?.available_providers || {});

    const loadConfig = useCallback(async () => {
        try {
            const response = await axios.get(`${backendUrl}/api/config`);
            setConfig(response.data);
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }, [backendUrl]);

    const loadMcp = useCallback(async () => {
        try {
            const response = await axios.get(`${backendUrl}/api/uefn/mcp/status`);
            setMcp(response.data);
            cacheWrite(CACHE_KEY_MCP, response.data);
        } catch {
            // keep cached value, don't null it out
        }
    }, [backendUrl]);

    const loadAiStatus = useCallback(async () => {
        try {
            const response = await axios.get(`${backendUrl}/api/chat/status`);
            const data = response.data;
            setAiStatus(data);
            setBackendProviders(data?.available_providers || {});
            setProviderModels(data?.provider_models || {});
            if (data?.provider) {
                setActiveProvider(data.provider);
                setSelectedProvider(data.provider);
            }
            if (data?.model) {
                setActiveModel(data.model);
                const nextProvider = data?.provider || selectedProvider;
                setSelectedModel(data?.provider_models?.[nextProvider] || data.model);
            }
            // Cache for next mount
            cacheWrite(CACHE_KEY_AI, data);
        } catch {
            // keep cached value, don't null it out
        }
    }, [backendUrl, selectedProvider]);

    useEffect(() => {
        void loadConfig();
        void loadMcp();
        void loadAiStatus();
    }, [loadAiStatus, loadConfig, loadMcp]);

    const testMcpCommand = useCallback(async () => {
        setMcpTest(null);
        try {
            const response = await axios.post(`${backendUrl}/api/uefn/mcp/command`, {
                command: 'get_level_info',
                params: {}
            });
            if (response.data?.success) {
                setMcpTest(`OK: ${JSON.stringify(response.data.result).slice(0, 280)}...`);
            } else {
                setMcpTest(`Error: ${response.data?.error || JSON.stringify(response.data)}`);
            }
        } catch (e: any) {
            setMcpTest(e?.response?.data?.error || e?.message || 'Request failed');
        }
    }, [backendUrl]);

    // Save ALL keys + active provider + model at once
    const saveAllAiSettings = useCallback(async () => {
        setSavingAi(true);
        setAiSaved('');
        try {
            // Build keys object with only non-empty values
            const keys: Record<string, string> = {};
            for (const [prov, val] of Object.entries(keyInputs)) {
                if (val.trim()) keys[prov] = val.trim();
            }

            const nextProviderModels = {
                ...providerModels,
                [selectedProvider]: selectedModel,
            };

            await axios.post(`${backendUrl}/api/settings/ai`, {
                provider: selectedProvider,
                model: selectedModel,
                keys, // batch save all keys
                provider_models: nextProviderModels,
            });

            setAiSaved('All settings saved!');
            setProviderModels(nextProviderModels);
            // Clear key inputs after save (keys are now stored server-side)
            setKeyInputs({ groq: '', cerebras: '', gemini: '' });
            // Reload status to reflect changes
            await loadAiStatus();
            setTimeout(() => setAiSaved(''), 4000);
        } catch (e: any) {
            setAiSaved('Failed to save — check backend console.');
            console.error('Failed to save AI settings:', e);
        } finally {
            setSavingAi(false);
        }
    }, [backendUrl, keyInputs, providerModels, selectedModel, selectedProvider, loadAiStatus]);

    const handleRefreshAll = useCallback(() => {
        void loadConfig();
        void loadMcp();
        void loadAiStatus();
    }, [loadAiStatus, loadConfig, loadMcp]);

    const handleSaveLocalSettings = useCallback(() => {
        setLoading(true);
        try {
            localStorage.setItem('appConfig', JSON.stringify(config));
            setSaved(true);
            window.setTimeout(() => setSaved(false), 3000);
        } finally {
            setLoading(false);
        }
    }, [config]);

    // Activate a specific provider (set as active)
    function selectActiveProvider(prov: string) {
        setSelectedProvider(prov);
        const info = backendProviders[prov] || STATIC_PROVIDERS[prov];
        if (info) {
            setSelectedModel(providerModels[prov] || info.default_model || '');
        }
    }

    function toggleKeyVisibility(prov: string) {
        setKeyVisible(prev => ({ ...prev, [prov]: !prev[prov] }));
    }

    function setKeyInput(prov: string, val: string) {
        setKeyInputs(prev => ({ ...prev, [prov]: val }));
    }

    // Merge static + backend provider data
    function getProviderInfo(prov: string): ProviderInfo & { key_env: string } {
        const backend = backendProviders[prov];
        const stat = STATIC_PROVIDERS[prov];
        return {
            label: backend?.label || stat?.label || prov,
            hint: backend?.hint || stat?.hint || '',
            has_key: backend?.has_key || false,
            models: (backend?.models?.length ? backend.models : stat?.models) || [],
            default_model: backend?.default_model || stat?.default_model || '',
            key_env: stat?.key_env || '',
        };
    }

    const uefn = config?.uefn || {};

    // Models for the currently selected active provider
    const currentInfo = getProviderInfo(selectedProvider);
    const availableModels = currentInfo.models || [];

    return (
        <div className="settings-panel">
            <div className="panel-header">
                <h2>Settings</h2>
                <p>AI configuration, UEFN MCP bridge, and app info</p>
            </div>

            <div className="settings-content">
                {/* AI Chat Configuration */}
                <section className="settings-section ai-section">
                    <h3>
                        <Sparkles size={18} style={{ verticalAlign: 'middle', marginRight: 8 }} />
                        AI Chat Provider
                    </h3>

                    {/* Status bar */}
                    <div className="ai-status-card">
                        <div className="ai-status-row">
                            <span className="label">Status</span>
                            <span className={`value ${aiStatus?.ai_enabled ? 'ok' : 'warn'}`}>
                                {aiStatus?.ai_enabled
                                    ? <><CheckCircle size={14} /> {getProviderInfo(activeProvider).label}</>
                                    : <><AlertCircle size={14} /> Basic Mode (keyword matching)</>}
                            </span>
                        </div>
                        {activeModel && aiStatus?.ai_enabled && (
                            <div className="ai-status-row">
                                <span className="label">Active model</span>
                                <span className="value">{activeModel}</span>
                            </div>
                        )}
                        {!aiStatus?.has_openai_pkg && aiStatus !== null && (
                            <div className="ai-status-row">
                                <span className="label">Warning</span>
                                <span className="value warn">
                                    <code>openai</code> package not installed. Run: <code>pip install openai</code>
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Provider cards — all shown at once */}
                    <div className="provider-cards">
                        {['groq', 'cerebras', 'gemini', 'ollama'].map(prov => {
                            const info = getProviderInfo(prov);
                            const isActive = prov === activeProvider && aiStatus?.ai_enabled;
                            const isSelected = prov === selectedProvider;
                            const needsKey = prov !== 'ollama';
                            const hasKey = info.has_key;
                            const keyInput = keyInputs[prov] || '';

                            return (
                                <div
                                    key={prov}
                                    className={`provider-card ${isSelected ? 'selected' : ''} ${isActive ? 'active' : ''}`}
                                    onClick={() => selectActiveProvider(prov)}
                                >
                                    <div className="provider-card-header">
                                        <span className="provider-card-name">{info.label}</span>
                                        <div className="provider-card-badges">
                                            {isActive && <span className="badge badge-active">Active</span>}
                                            {hasKey && !isActive && <span className="badge badge-configured">Key Set</span>}
                                            {!hasKey && needsKey && <span className="badge badge-missing">No Key</span>}
                                            {prov === 'ollama' && aiStatus?.ollama_running && <span className="badge badge-configured">Running</span>}
                                            {prov === 'ollama' && !aiStatus?.ollama_running && <span className="badge badge-missing">Offline</span>}
                                        </div>
                                    </div>
                                    <p className="provider-card-hint">
                                        <Zap size={12} /> {info.hint}
                                    </p>

                                    {/* API key input for non-Ollama */}
                                    {needsKey && isSelected && (
                                        <div className="provider-key-row" onClick={e => e.stopPropagation()}>
                                            <label><Key size={12} /> API Key {hasKey ? '(saved — enter new to replace)' : '(required)'}:</label>
                                            <div className="key-input-wrap">
                                                <input
                                                    type={keyVisible[prov] ? 'text' : 'password'}
                                                    value={keyInput}
                                                    onChange={e => setKeyInput(prov, e.target.value)}
                                                    placeholder={hasKey ? '••••••••••••' : 'Paste your free API key'}
                                                    className="api-key-input"
                                                />
                                                <button type="button" className="key-vis-btn" onClick={() => toggleKeyVisibility(prov)} title="Toggle visibility">
                                                    {keyVisible[prov] ? <EyeOff size={14} /> : <Eye size={14} />}
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Ollama setup hint */}
                                    {prov === 'ollama' && isSelected && !aiStatus?.ollama_running && (
                                        <div className="ollama-hint-inline" onClick={e => e.stopPropagation()}>
                                            <p>Install from <strong>ollama.com</strong>, then run:</p>
                                            <code>ollama pull llama3.1 && ollama serve</code>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Model picker for selected provider */}
                    <div className="ai-model-row">
                        <label htmlFor="ai-model">Model for {getProviderInfo(selectedProvider).label}:</label>
                        {availableModels.length > 0 ? (
                            <select
                                id="ai-model"
                                value={selectedModel}
                                onChange={e => {
                                    const value = e.target.value;
                                    setSelectedModel(value);
                                    setProviderModels(prev => ({ ...prev, [selectedProvider]: value }));
                                }}
                                className="model-select"
                            >
                                {availableModels.map(m => (
                                    <option key={m} value={m}>{m}</option>
                                ))}
                            </select>
                        ) : (
                            <input
                                id="ai-model"
                                type="text"
                                value={selectedModel}
                                onChange={e => {
                                    const value = e.target.value;
                                    setSelectedModel(value);
                                    setProviderModels(prev => ({ ...prev, [selectedProvider]: value }));
                                }}
                                placeholder={currentInfo.default_model || 'model name'}
                                className="model-input"
                            />
                        )}
                    </div>

                    {/* Save / Refresh */}
                    <div className="ai-actions-row">
                        <button
                            type="button"
                            className="save-key-btn primary"
                            onClick={saveAllAiSettings}
                            disabled={savingAi}
                        >
                            {savingAi ? 'Saving...' : 'Apply & Save'}
                        </button>
                        <button
                            type="button"
                            className="link-btn refresh-ai-btn"
                            onClick={() => void loadAiStatus()}
                        >
                            <RefreshCw size={14} /> Refresh
                        </button>
                        {aiSaved && <span className="saved-indicator">{aiSaved}</span>}
                    </div>
                </section>

                <section className="settings-section">
                    <h3>Application Info</h3>
                    {appInfo && (
                        <div className="info-grid">
                            <div className="info-item">
                                <span className="label">Name:</span>
                                <span className="value">{appInfo.name}</span>
                            </div>
                            <div className="info-item">
                                <span className="label">Version:</span>
                                <span className="value">{appInfo.version}</span>
                            </div>
                            <div className="info-item">
                                <span className="label">Mode:</span>
                                <span className="value">{appInfo.isDev ? 'Development' : 'Production'}</span>
                            </div>
                            <div className="info-item">
                                <span className="label">Platform:</span>
                                <span className="value">{window.navigator.platform}</span>
                            </div>
                        </div>
                    )}
                </section>

                <section className="settings-section mcp-section">
                    <h3>
                        <Plug size={18} style={{ verticalAlign: 'middle', marginRight: 8 }} />
                        UEFN MCP listener
                    </h3>
                    <p className="mcp-hint">
                        The in-editor HTTP listener connects this app to the UEFN editor.
                        The backend will try to auto-start it. If it can't connect, open UEFN
                        and run <code>uefn_listener.py</code> from the Python console.
                    </p>
                    <div className="mcp-status-card">
                        <div className="mcp-row">
                            <span className="label">Listener</span>
                            <span className={mcp?.connected ? 'value ok' : 'value warn'}>
                                {mcp?.connected ? `Online (port ${mcp?.port ?? '?'})` : 'Not reachable'}
                            </span>
                        </div>
                        {mcp?.health?.version && (
                            <div className="mcp-row">
                                <span className="label">Protocol</span>
                                <span className="value">{mcp.health.version}</span>
                            </div>
                        )}
                        {mcp?.health?.commands && (
                            <div className="mcp-row">
                                <span className="label">Commands</span>
                                <span className="value">{mcp.health.commands.length} registered</span>
                            </div>
                        )}
                        <div className="mcp-actions">
                            <button type="button" className="link-btn" onClick={() => void loadMcp()}>
                                <RefreshCw size={16} />
                                Refresh status
                            </button>
                            <button type="button" className="link-btn" onClick={() => void testMcpCommand()} disabled={!mcp?.connected}>
                                <Terminal size={16} />
                                Test get_level_info
                            </button>
                        </div>
                        {mcpTest && (
                            <pre className="mcp-test-out">{mcpTest}</pre>
                        )}
                    </div>
                </section>

                <section className="settings-section">
                    <h3>Backend snapshot</h3>
                    <div className="config-grid">
                        <div className="config-item">
                            <label>UEFN bridge</label>
                            <input
                                type="text"
                                readOnly
                                className="config-input"
                                value={uefn.connected ? `connected (${uefn.listener_port ?? uefn.port})` : 'offline'}
                            />
                        </div>
                        {config && Object.entries(config).filter(([k]) => k !== 'uefn').map(([key, value]: [string, any]) => (
                            <div key={key} className="config-item">
                                <label>{key}</label>
                                <input
                                    type="text"
                                    value={typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                    readOnly
                                    className="config-input"
                                />
                            </div>
                        ))}
                    </div>
                </section>

                <div className="settings-actions">
                    <button type="button" className="action-btn refresh" onClick={handleRefreshAll}>
                        <RefreshCw size={18} />
                        Reload Config
                    </button>
                    <button type="button" className="action-btn save" onClick={handleSaveLocalSettings} disabled={loading}>
                        <Save size={18} />
                        {loading ? 'Saving...' : 'Save Settings'}
                    </button>
                    {saved && <span className="saved-indicator">Saved</span>}
                </div>
            </div>
        </div>
    );
}

export default SettingsPanel;
