import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Search, Zap, ChevronRight, Tag, Layers, Info, Terminal } from 'lucide-react';
import axios from 'axios';
import '../styles/ToolDashboard.css';

interface Tool {
    id: string;
    name: string;
    category: string;
    description: string;
    short_description: string;
    parameters: any[];
    tags: string[];
}

function normalizeCategoryLabel(cat: string): string {
    const t = (cat || '').trim();
    if (!t) return 'Uncategorized';
    return t.replace(/\b\w/g, c => c.toUpperCase());
}

function categoryKey(cat: string): string {
    return (cat || '').trim().toLowerCase();
}

/** Generate a "What this tool does" section based on description + tags. */
function generateCapabilities(tool: Tool): string[] {
    const caps: string[] = [];
    const desc = (tool.description || '').toLowerCase();

    // Analyze description for capabilities
    if (desc.includes('batch') || desc.includes('bulk') || desc.includes('all selected') || desc.includes('every'))
        caps.push('Works on multiple actors/assets at once');
    if (desc.includes('json') || desc.includes('report') || desc.includes('export'))
        caps.push('Produces structured output (JSON/report) for further analysis');
    if (desc.includes('configurable') || desc.includes('parameter'))
        caps.push('Highly configurable with multiple options');
    if (desc.includes('preview') || desc.includes('dry run') || desc.includes('without'))
        caps.push('Safe to run — previews changes before applying');
    if (desc.includes('undo') || desc.includes('restore') || desc.includes('revert'))
        caps.push('Supports undo/restore operations');
    if (desc.includes('automat') || desc.includes('auto-'))
        caps.push('Automated — runs with minimal manual input');
    if (desc.includes('procedur') || desc.includes('generat'))
        caps.push('Procedurally generates content');
    if (desc.includes('verse'))
        caps.push('Generates or works with Verse code');
    if (desc.includes('performance') || desc.includes('optimi') || desc.includes('memory'))
        caps.push('Helps optimize project performance');
    if (desc.includes('cleanup') || desc.includes('organiz') || desc.includes('clean'))
        caps.push('Helps keep your project organized');

    if (caps.length === 0) {
        caps.push('Execute directly from the dashboard');
    }
    return caps;
}

/** Get a "When to use" hint based on tool category and tags. */
function getUsageHint(tool: Tool): string {
    const cat = (tool.category || '').toLowerCase();
    const desc = (tool.description || '').toLowerCase();

    if (cat.includes('api')) return 'Use when you need to understand what objects, classes, or API surfaces are available in your UEFN project.';
    if (cat.includes('bulk') || cat.includes('ops')) return 'Use when you have multiple actors selected and want to transform, align, or modify them together.';
    if (cat.includes('material')) return 'Use when you want to change colors, materials, or visual appearance of actors in your level.';
    if (cat.includes('procedural')) return 'Use when you want to generate content (arenas, scatter, patterns) procedurally instead of placing by hand.';
    if (cat.includes('asset')) return 'Use when managing, importing, organizing, or renaming assets in your content browser.';
    if (cat.includes('snapshot')) return 'Use when you want to save or restore the state of your level — like checkpoints for your work.';
    if (cat.includes('optimization') || cat.includes('memory')) return 'Use when your project feels slow or you want to check memory/performance budgets.';
    if (cat.includes('pattern')) return 'Use when you want to place objects in geometric patterns (grid, circle, spiral, etc.).';
    if (cat.includes('verse')) return 'Use when working with Verse devices, scripting, or generating game logic code.';
    if (cat.includes('text') || cat.includes('sign')) return 'Use when you want to add text labels, signs, or coordinate grids to your level.';
    if (cat.includes('screenshot')) return 'Use when you need to capture viewport images for documentation or reference.';
    if (cat.includes('audit') || cat.includes('reference')) return 'Use when cleaning up your project — finding unused assets, duplicates, or broken references.';
    if (cat.includes('project')) return 'Use when setting up a new project structure or organizing loose files.';
    if (cat.includes('mcp')) return 'Use when managing the MCP bridge connection between this app and the UEFN editor.';
    if (desc.includes('test')) return 'Use to verify that all tools are working correctly.';
    return 'Execute this tool to perform the described operation in your UEFN project.';
}

function ToolDashboard({ backendUrl }: { backendUrl: string }) {
    const [tools, setTools] = useState<Tool[]>([]);
    const [selectedCategoryKey, setSelectedCategoryKey] = useState<string>('');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedTool, setSelectedTool] = useState<Tool | null>(null);
    const [executing, setExecuting] = useState(false);
    const [results, setResults] = useState<any>(null);
    const [parameters, setParameters] = useState<Record<string, any>>({});

    const loadTools = useCallback(async () => {
        try {
            const response = await axios.get(`${backendUrl}/api/tools`);
            setTools(response.data.tools || []);
        } catch (error) {
            console.error('Failed to load tools:', error);
        }
    }, [backendUrl]);

    useEffect(() => {
        void loadTools();
    }, [loadTools]);

    const categoryOptions = useMemo(() => {
        const map = new Map<string, { label: string; count: number }>();
        tools.forEach(t => {
            const key = categoryKey(t.category);
            const label = normalizeCategoryLabel(t.category);
            const prev = map.get(key);
            if (prev) {
                map.set(key, { label: prev.label, count: prev.count + 1 });
            } else {
                map.set(key, { label, count: 1 });
            }
        });
        return Array.from(map.entries())
            .map(([key, v]) => ({ key, label: v.label, count: v.count }))
            .sort((a, b) => a.label.localeCompare(b.label));
    }, [tools]);

    function getFilteredTools() {
        let filtered = tools;

        if (selectedCategoryKey) {
            filtered = filtered.filter(t => categoryKey(t.category) === selectedCategoryKey);
        }

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(t =>
                t.name.toLowerCase().includes(q) ||
                (t.description && t.description.toLowerCase().includes(q)) ||
                (t.short_description && t.short_description.toLowerCase().includes(q)) ||
                (t.tags && t.tags.some(tag => tag.toLowerCase().includes(q)))
            );
        }

        return filtered;
    }

    function toolSummary(t: Tool): string {
        const s = (t.short_description || '').trim();
        const d = (t.description || '').trim();
        if (s && s !== d) return s;
        if (d) return d.length > 160 ? `${d.slice(0, 157)}...` : d;
        return 'No description yet for this tool.';
    }

    async function executeTool() {
        if (!selectedTool) return;
        const registryKey = selectedTool.id || selectedTool.name;
        setExecuting(true);
        try {
            const response = await axios.post(
                `${backendUrl}/api/tools/${encodeURIComponent(registryKey)}/execute`,
                parameters
            );
            setResults(response.data);
        } catch (error) {
            setResults({ error: 'Failed to execute tool', details: error });
        } finally {
            setExecuting(false);
        }
    }

    const filtered = getFilteredTools();

    return (
        <div className="tool-dashboard">
            <div className="dashboard-header">
                <h2>Tool Dashboard</h2>
                <p>Discover and run {tools.length} UEFN Toolbelt tools. Select a tool to see its full description, capabilities, and parameters.</p>
            </div>

            <div className="dashboard-content">
                <aside className="tools-sidebar">
                    <div className="search-box">
                        <Search size={18} />
                        <input
                            type="text"
                            placeholder="Search tools..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>

                    <div className="categories">
                        <h3>Categories</h3>
                        <button
                            type="button"
                            className={`category-btn ${!selectedCategoryKey ? 'active' : ''}`}
                            onClick={() => setSelectedCategoryKey('')}
                        >
                            All <span className="cat-count">{tools.length}</span>
                        </button>
                        {categoryOptions.map(({ key, label, count }) => (
                            <button
                                type="button"
                                key={key}
                                className={`category-btn ${selectedCategoryKey === key ? 'active' : ''}`}
                                onClick={() => setSelectedCategoryKey(key)}
                            >
                                {label} <span className="cat-count">{count}</span>
                            </button>
                        ))}
                    </div>
                </aside>

                <div className="dashboard-main">
                    <section className="tools-list-panel" aria-label="Tool list">
                        <div className="tools-header">
                            <h3>Available tools</h3>
                            <span className="tools-count">{filtered.length}</span>
                        </div>
                        <div className="tools-grid">
                            {filtered.map(tool => (
                                <button
                                    type="button"
                                    key={tool.id}
                                    className={`tool-card ${selectedTool?.id === tool.id ? 'selected' : ''}`}
                                    onClick={() => {
                                        setSelectedTool(tool);
                                        setParameters({});
                                        setResults(null);
                                    }}
                                >
                                    <div className="tool-card-top">
                                        <span className="tool-name">{tool.name}</span>
                                        <ChevronRight size={16} className="tool-chevron" />
                                    </div>
                                    <p className="tool-summary">{toolSummary(tool)}</p>
                                    <div className="tool-card-meta">
                                        <span className="category-pill">{normalizeCategoryLabel(tool.category)}</span>
                                        {tool.tags && tool.tags.length > 0 && (
                                            <span className="tool-tag-preview">{tool.tags.slice(0, 2).join(' / ')}</span>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                    </section>

                    <section className="tool-details-panel" aria-label="Tool details">
                        {!selectedTool ? (
                            <div className="tool-details-empty">
                                <p className="empty-title">Select a tool</p>
                                <p className="empty-sub">
                                    Pick a tool from the list to see its full description, capabilities, parameters, and run it.
                                </p>
                            </div>
                        ) : (
                            <>
                                <div className="details-head">
                                    <div>
                                        <h3>{selectedTool.name}</h3>
                                        <p className="details-category">{normalizeCategoryLabel(selectedTool.category)}</p>
                                    </div>
                                </div>

                                <div className="details-body">
                                    {/* Short description as lead */}
                                    {selectedTool.short_description && (
                                        <p className="details-lead">{selectedTool.short_description}</p>
                                    )}

                                    {/* Full description */}
                                    <div className="details-section">
                                        <div className="section-label">
                                            <Info size={14} />
                                            <span>Description</span>
                                        </div>
                                        <p className="details-desc">{selectedTool.description || 'No extended description.'}</p>
                                    </div>

                                    {/* Capabilities */}
                                    <div className="details-section">
                                        <div className="section-label">
                                            <Layers size={14} />
                                            <span>Capabilities</span>
                                        </div>
                                        <ul className="capabilities-list">
                                            {generateCapabilities(selectedTool).map((cap, i) => (
                                                <li key={i}>{cap}</li>
                                            ))}
                                        </ul>
                                    </div>

                                    {/* When to use */}
                                    <div className="details-section">
                                        <div className="section-label">
                                            <Terminal size={14} />
                                            <span>When to use</span>
                                        </div>
                                        <p className="details-hint">{getUsageHint(selectedTool)}</p>
                                    </div>
                                </div>

                                {/* Tags */}
                                {selectedTool.tags && selectedTool.tags.length > 0 && (
                                    <div className="details-tags">
                                        <div className="section-label">
                                            <Tag size={14} />
                                            <span>Tags</span>
                                        </div>
                                        <div className="tags-row">
                                            {selectedTool.tags.map(tag => (
                                                <span key={tag} className="tag-chip">{tag}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Parameters */}
                                {selectedTool.parameters && selectedTool.parameters.length > 0 && (
                                    <div className="parameters-block">
                                        <h4>Parameters</h4>
                                        {selectedTool.parameters.map((param: any) => (
                                            <div key={param.name} className="parameter-input">
                                                <label htmlFor={`p-${param.name}`}>{param.name}</label>
                                                <input
                                                    id={`p-${param.name}`}
                                                    type="text"
                                                    placeholder={param.description || ''}
                                                    value={parameters[param.name] ?? ''}
                                                    onChange={(e) => setParameters({
                                                        ...parameters,
                                                        [param.name]: e.target.value
                                                    })}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                )}

                                <button
                                    type="button"
                                    className="execute-btn"
                                    onClick={executeTool}
                                    disabled={executing}
                                >
                                    <Zap size={18} />
                                    {executing ? 'Running...' : 'Run tool'}
                                </button>

                                {results && (
                                    <div className="results-block">
                                        <h4>Result</h4>
                                        <pre>{JSON.stringify(results, null, 2)}</pre>
                                    </div>
                                )}
                            </>
                        )}
                    </section>
                </div>
            </div>
        </div>
    );
}

export default ToolDashboard;
