import React, { useRef, useMemo, useEffect, useState } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { OrbitControls, Environment, Grid, useGLTF, Html } from '@react-three/drei';
import * as THREE from 'three';

export type ViewMode = 'solid' | 'wireframe' | 'normals' | 'matcap' | 'uv';

interface ModelViewer3DProps {
    glbUrl: string;
    viewMode: ViewMode;
    autoRotate?: boolean;
    onMeshStats?: (stats: { vertices: number; triangles: number; bounds: number[] }) => void;
    onScreenshot?: () => void;
    screenshotTrigger?: number;
}

/** Matcap texture generated procedurally */
function useMatcapTexture(): THREE.Texture {
    return useMemo(() => {
        const size = 256;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d')!;
        const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
        gradient.addColorStop(0, '#e8e0ff');
        gradient.addColorStop(0.4, '#9080c0');
        gradient.addColorStop(0.8, '#4a3a70');
        gradient.addColorStop(1, '#1a1030');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, size, size);
        const tex = new THREE.CanvasTexture(canvas);
        tex.needsUpdate = true;
        return tex;
    }, []);
}

/** UV checker pattern texture */
function useUVCheckerTexture(): THREE.Texture {
    return useMemo(() => {
        const size = 512;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d')!;
        const cellSize = size / 16;
        for (let y = 0; y < 16; y++) {
            for (let x = 0; x < 16; x++) {
                ctx.fillStyle = (x + y) % 2 === 0 ? '#404050' : '#808090';
                ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
            }
        }
        // Grid lines
        ctx.strokeStyle = '#60607080';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 16; i++) {
            ctx.beginPath();
            ctx.moveTo(i * cellSize, 0); ctx.lineTo(i * cellSize, size);
            ctx.moveTo(0, i * cellSize); ctx.lineTo(size, i * cellSize);
            ctx.stroke();
        }
        const tex = new THREE.CanvasTexture(canvas);
        tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
        tex.needsUpdate = true;
        return tex;
    }, []);
}

/** The loaded GLB model with view mode switching */
function Model({ url, viewMode, onStats }: {
    url: string;
    viewMode: ViewMode;
    onStats?: (s: { vertices: number; triangles: number; bounds: number[] }) => void;
}) {
    const { scene } = useGLTF(url);
    const groupRef = useRef<THREE.Group>(null);
    const matcapTex = useMatcapTexture();
    const uvTex = useUVCheckerTexture();

    // Center and ground the model
    useEffect(() => {
        if (!groupRef.current) return;
        const box = new THREE.Box3().setFromObject(groupRef.current);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());

        groupRef.current.position.set(-center.x, -box.min.y, -center.z);

        if (onStats) {
            let verts = 0, tris = 0;
            groupRef.current.traverse((child) => {
                if ((child as THREE.Mesh).isMesh) {
                    const geo = (child as THREE.Mesh).geometry;
                    if (geo.index) tris += geo.index.count / 3;
                    else if (geo.attributes.position) tris += geo.attributes.position.count / 3;
                    if (geo.attributes.position) verts += geo.attributes.position.count;
                }
            });
            onStats({ vertices: verts, triangles: Math.round(tris), bounds: [size.x, size.y, size.z] });
        }
    }, [scene, onStats]);

    // Apply view mode materials
    useEffect(() => {
        if (!groupRef.current) return;

        groupRef.current.traverse((child) => {
            if (!(child as THREE.Mesh).isMesh) return;
            const mesh = child as THREE.Mesh;

            // Store original material
            if (!(mesh.userData as any)._origMat) {
                (mesh.userData as any)._origMat = mesh.material;
            }

            switch (viewMode) {
                case 'solid':
                    mesh.material = (mesh.userData as any)._origMat;
                    if (Array.isArray(mesh.material)) {
                        mesh.material.forEach((m: THREE.Material) => { (m as any).wireframe = false; });
                    } else {
                        (mesh.material as any).wireframe = false;
                    }
                    break;
                case 'wireframe':
                    mesh.material = (mesh.userData as any)._origMat;
                    if (Array.isArray(mesh.material)) {
                        mesh.material.forEach((m: THREE.Material) => { (m as any).wireframe = true; });
                    } else {
                        (mesh.material as any).wireframe = true;
                    }
                    break;
                case 'normals':
                    mesh.material = new THREE.MeshNormalMaterial();
                    break;
                case 'matcap':
                    mesh.material = new THREE.MeshMatcapMaterial({ matcap: matcapTex });
                    break;
                case 'uv':
                    mesh.material = new THREE.MeshStandardMaterial({ map: uvTex });
                    break;
            }
        });

        return () => {
            // Restore on unmount
            if (groupRef.current) {
                groupRef.current.traverse((child) => {
                    if ((child as THREE.Mesh).isMesh) {
                        const mesh = child as THREE.Mesh;
                        if ((mesh.userData as any)._origMat) {
                            mesh.material = (mesh.userData as any)._origMat;
                        }
                    }
                });
            }
        };
    }, [viewMode, matcapTex, uvTex]);

    return (
        <group ref={groupRef}>
            <primitive object={scene.clone(true)} />
        </group>
    );
}

/** Screenshot helper */
function ScreenshotCapture({ trigger, onCapture }: { trigger: number; onCapture: () => void }) {
    const { gl } = useThree();

    useEffect(() => {
        if (trigger > 0) {
            const dataUrl = gl.domElement.toDataURL('image/png');
            const link = document.createElement('a');
            link.download = `model-screenshot-${Date.now()}.png`;
            link.href = dataUrl;
            link.click();
            onCapture();
        }
    }, [trigger, gl, onCapture]);

    return null;
}

/** Camera preset helper */
export function useCameraPresets() {
    const presets: Record<string, [number, number, number]> = {
        front: [0, 1, 3],
        back: [0, 1, -3],
        left: [-3, 1, 0],
        right: [3, 1, 0],
        top: [0, 4, 0.01],
        perspective: [2, 2, 2],
    };
    return presets;
}

export default function ModelViewer3D({
    glbUrl, viewMode, autoRotate = true, onMeshStats, screenshotTrigger = 0
}: ModelViewer3DProps) {
    const [error, setError] = useState<string | null>(null);

    if (!glbUrl) {
        return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#555' }}>No model loaded</div>;
    }

    return (
        <Canvas
            camera={{ position: [2, 2, 2], fov: 45 }}
            gl={{ preserveDrawingBuffer: true, antialias: true }}
            onCreated={({ gl }) => {
                gl.outputColorSpace = THREE.SRGBColorSpace;
                gl.toneMapping = THREE.ACESFilmicToneMapping;
            }}
            style={{ background: '#0a0a15' }}
        >
            <ambientLight intensity={0.4} />
            <directionalLight position={[5, 8, 5]} intensity={1.2} castShadow />
            <directionalLight position={[-3, 4, -5]} intensity={0.4} />

            <React.Suspense fallback={
                <Html center><div style={{ color: '#888', fontSize: 14 }}>Loading model...</div></Html>
            }>
                <Model url={glbUrl} viewMode={viewMode} onStats={onMeshStats} />
            </React.Suspense>

            <Grid
                args={[20, 20]}
                cellSize={0.5}
                cellThickness={0.5}
                cellColor="#2a2a4a"
                sectionSize={2}
                sectionThickness={1}
                sectionColor="#3a3a5a"
                fadeDistance={15}
                fadeStrength={1}
                infiniteGrid
            />

            <OrbitControls
                autoRotate={autoRotate}
                autoRotateSpeed={1}
                enableDamping
                dampingFactor={0.1}
                minDistance={0.5}
                maxDistance={20}
            />

            <ScreenshotCapture trigger={screenshotTrigger} onCapture={() => {}} />
        </Canvas>
    );
}
