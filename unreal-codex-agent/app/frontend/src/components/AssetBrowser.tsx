import React, { useState, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import { Box, Layers, Info } from 'lucide-react';
import '../styles/AssetBrowser.css';

interface AssetRecord {
    id?: string;
    name?: string;
    type?: string;
    category?: string;
    description?: string;
    path?: string;
    thumbnail?: string;
    trust_score?: number;
    dimensions?: Record<string, number>;
    composite_asset?: boolean;
    viewer_model_url?: string;
    viewer_note?: string;
}

declare global {
    namespace JSX {
        interface IntrinsicElements {
            'model-viewer': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
                src?: string;
                alt?: string;
                'camera-controls'?: boolean;
                'shadow-intensity'?: string;
                'environment-image'?: string;
            };
        }
    }
}

function AssetBrowser({ backendUrl }: { backendUrl: string }) {
    const [assets, setAssets] = useState<AssetRecord[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [assetTypeFilter, setAssetTypeFilter] = useState('');
    const [selectedAsset, setSelectedAsset] = useState<AssetRecord | null>(null);

    const loadAssets = useCallback(async () => {
        try {
            const response = await axios.get(`${backendUrl}/api/assets/shortlist`);
            setAssets(response.data.assets || []);
        } catch (error) {
            console.error('Failed to load assets:', error);
        }
    }, [backendUrl]);

    useEffect(() => {
        void loadAssets();
    }, [loadAssets]);

    const filteredAssets = useMemo(() => {
        let filtered = assets;

        if (assetTypeFilter) {
            filtered = filtered.filter(a => a.type === assetTypeFilter);
        }

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(a =>
                (a.name && a.name.toLowerCase().includes(q)) ||
                (a.path && a.path.toLowerCase().includes(q)) ||
                (a.type && a.type.toLowerCase().includes(q)) ||
                (a.description && a.description.toLowerCase().includes(q))
            );
        }

        return filtered;
    }, [assets, assetTypeFilter, searchQuery]);

    const assetTypes = useMemo(() => [...new Set(assets.map(a => a.type).filter(Boolean))] as string[], [assets]);

    return (
        <div className="asset-browser">
            <div className="browser-header">
                <h2>Asset browser</h2>
                <p>
                    Each entry here is meant to represent a <strong>whole composite</strong> you are working on (one
                    publishable unit), not every mesh layer. In a full pipeline, you would register a finished build
                    from UEFN so the AI and reviewers inspect the same assembled asset.
                </p>
                <div className="browser-callout">
                    <Info size={18} />
                    <span>
                        Roadmap: bind this list to your project catalog and attach one GLB/GLTF per composite for 3D
                        review (below).
                    </span>
                </div>
            </div>

            <div className="browser-toolbar">
                <div className="search-box">
                    <input
                        type="text"
                        placeholder="Search by name, type, or description…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <select
                    className="filter-select"
                    value={assetTypeFilter}
                    onChange={(e) => setAssetTypeFilter(e.target.value)}
                >
                    <option value="">All types</option>
                    {assetTypes.map(type => (
                        <option key={type} value={type}>{type}</option>
                    ))}
                </select>
            </div>

            <div className="browser-content">
                <div className="assets-column">
                    <div className="column-title">
                        <Layers size={18} />
                        Composites ({filteredAssets.length})
                    </div>
                    <div className="assets-grid">
                        {filteredAssets.length === 0 ? (
                            <div className="assets-empty">
                                <Box size={36} strokeWidth={1.25} />
                                <p>No assets in the shortlist yet.</p>
                                <small>Add entries via your pipeline or seed data/catalog/shortlist.json on the backend.</small>
                            </div>
                        ) : (
                            filteredAssets.map((asset, idx) => (
                                <button
                                    type="button"
                                    key={asset.id || `${asset.name}-${idx}`}
                                    className={`asset-card ${selectedAsset?.id === asset.id ? 'selected' : ''}`}
                                    onClick={() => setSelectedAsset(asset)}
                                >
                                    <div className="asset-thumbnail">
                                        {asset.thumbnail ? (
                                            <img src={asset.thumbnail} alt={asset.name || ''} />
                                        ) : (
                                            <div className="placeholder">{asset.type || 'asset'}</div>
                                        )}
                                    </div>
                                    <div className="asset-info">
                                        <h4>{asset.name}</h4>
                                        <p className="asset-type">{asset.type}</p>
                                        {asset.composite_asset && (
                                            <span className="composite-badge">Composite</span>
                                        )}
                                    </div>
                                </button>
                            ))
                        )}
                    </div>
                </div>

                {selectedAsset && (
                    <div className="asset-detail-column">
                        <div className="asset-preview-card">
                            <h3>{selectedAsset.name}</h3>
                            {selectedAsset.description && (
                                <p className="asset-desc">{selectedAsset.description}</p>
                            )}

                            <div className="viewer-panel">
                                <div className="viewer-title">3D preview</div>
                                {selectedAsset.viewer_model_url ? (
                                    <>
                                        <model-viewer
                                            src={selectedAsset.viewer_model_url}
                                            alt={selectedAsset.name || 'Asset model'}
                                            camera-controls
                                            shadow-intensity="1"
                                            style={{ width: '100%', height: 'min(360px, 45vh)', borderRadius: '10px', background: '#0a0a0a' }}
                                        />
                                        {selectedAsset.viewer_note && (
                                            <p className="viewer-note">{selectedAsset.viewer_note}</p>
                                        )}
                                    </>
                                ) : (
                                    <div className="viewer-placeholder">
                                        <p>No GLB/GLTF URL on this asset yet.</p>
                                        <small>
                                            When your pipeline exports a composite, store <code>viewer_model_url</code> on
                                            the asset record so Codex can inspect the full model—not individual wall meshes.
                                        </small>
                                    </div>
                                )}
                            </div>

                            <div className="asset-properties">
                                {selectedAsset.type && (
                                    <div className="property">
                                        <span className="key">Type</span>
                                        <span className="value">{selectedAsset.type}</span>
                                    </div>
                                )}
                                {selectedAsset.path && (
                                    <div className="property">
                                        <span className="key">Path</span>
                                        <span className="value">{selectedAsset.path}</span>
                                    </div>
                                )}
                                {selectedAsset.dimensions && (
                                    <div className="property">
                                        <span className="key">Dimensions</span>
                                        <span className="value">{JSON.stringify(selectedAsset.dimensions)}</span>
                                    </div>
                                )}
                                {selectedAsset.trust_score != null && (
                                    <div className="property">
                                        <span className="key">Trust score</span>
                                        <span className="value">{(selectedAsset.trust_score * 100).toFixed(0)}%</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default AssetBrowser;
