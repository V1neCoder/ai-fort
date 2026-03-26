import React from 'react';

interface MeshStatsProps {
    vertices: number;
    triangles: number;
    bounds: number[];
    version?: number;
}

export default function MeshStats({ vertices, triangles, bounds, version }: MeshStatsProps) {
    const [w, h, d] = bounds.length >= 3
        ? bounds.map(v => (v * 100).toFixed(0))  // Convert to cm display
        : ['?', '?', '?'];

    return (
        <div className="mai-mesh-stats-panel">
            <div className="mai-stat">
                <span className="mai-stat-val">{vertices.toLocaleString()}</span>
                <span className="mai-stat-label">Vertices</span>
            </div>
            <div className="mai-stat">
                <span className="mai-stat-val">{triangles.toLocaleString()}</span>
                <span className="mai-stat-label">Triangles</span>
            </div>
            <div className="mai-stat">
                <span className="mai-stat-val">{w} x {d} x {h}</span>
                <span className="mai-stat-label">Size (cm)</span>
            </div>
            {version && (
                <div className="mai-stat">
                    <span className="mai-stat-val">v{version}</span>
                    <span className="mai-stat-label">Version</span>
                </div>
            )}
        </div>
    );
}
