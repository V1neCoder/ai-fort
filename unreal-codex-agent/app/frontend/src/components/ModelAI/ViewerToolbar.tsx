import React from 'react';
import { Camera, RotateCcw, Box, Grid3x3, Layers, Palette, Grid } from 'lucide-react';
import { ViewMode } from './ModelViewer3D';

interface ViewerToolbarProps {
    viewMode: ViewMode;
    onViewModeChange: (mode: ViewMode) => void;
    autoRotate: boolean;
    onAutoRotateToggle: () => void;
    onScreenshot: () => void;
    onCameraPreset: (preset: string) => void;
}

const VIEW_MODES: { mode: ViewMode; label: string; icon: React.ReactNode }[] = [
    { mode: 'solid', label: 'Solid', icon: <Box size={14} /> },
    { mode: 'wireframe', label: 'Wire', icon: <Grid3x3 size={14} /> },
    { mode: 'normals', label: 'Normals', icon: <Layers size={14} /> },
    { mode: 'matcap', label: 'Matcap', icon: <Palette size={14} /> },
    { mode: 'uv', label: 'UV', icon: <Grid size={14} /> },
];

const CAMERA_PRESETS = ['front', 'back', 'left', 'right', 'top', 'perspective'];

export default function ViewerToolbar({
    viewMode, onViewModeChange, autoRotate, onAutoRotateToggle, onScreenshot, onCameraPreset,
}: ViewerToolbarProps) {
    return (
        <div className="mai-toolbar">
            <div className="mai-toolbar-group">
                <span className="mai-toolbar-label">View:</span>
                {VIEW_MODES.map(({ mode, label, icon }) => (
                    <button key={mode}
                        className={`mai-toolbar-btn ${viewMode === mode ? 'active' : ''}`}
                        onClick={() => onViewModeChange(mode)}
                        title={label}>
                        {icon} {label}
                    </button>
                ))}
            </div>

            <div className="mai-toolbar-group">
                <span className="mai-toolbar-label">Camera:</span>
                {CAMERA_PRESETS.map(preset => (
                    <button key={preset}
                        className="mai-toolbar-btn small"
                        onClick={() => onCameraPreset(preset)}
                        title={preset}>
                        {preset.charAt(0).toUpperCase()}
                    </button>
                ))}
            </div>

            <div className="mai-toolbar-group">
                <button className={`mai-toolbar-btn ${autoRotate ? 'active' : ''}`}
                    onClick={onAutoRotateToggle} title="Auto-rotate">
                    <RotateCcw size={14} />
                </button>
                <button className="mai-toolbar-btn" onClick={onScreenshot} title="Screenshot">
                    <Camera size={14} />
                </button>
            </div>
        </div>
    );
}
