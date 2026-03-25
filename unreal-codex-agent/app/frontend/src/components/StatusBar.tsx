import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle, AlertCircle, Clock } from 'lucide-react';
import axios from 'axios';
import '../styles/StatusBar.css';

function StatusBar({ backendUrl, isConnected }: any) {
    const [status, setStatus] = useState({
        backend: 'checking',
        uefn: false,
        uefnPort: null as number | null,
        timestamp: new Date()
    });

    const checkStatus = useCallback(async () => {
        try {
            const response = await axios.get(`${backendUrl}/api/health`);
            setStatus({
                backend: response.data.status,
                uefn: Boolean(response.data.uefn_connected),
                uefnPort: response.data.uefn_listener_port ?? null,
                timestamp: new Date()
            });
        } catch (error) {
            setStatus(prev => ({ ...prev, backend: 'error' }));
        }
    }, [backendUrl]);

    useEffect(() => {
        const interval = setInterval(() => {
            void checkStatus();
        }, 5000);
        void checkStatus();
        return () => clearInterval(interval);
    }, [checkStatus]);

    return (
        <footer className="status-bar">
            <div className="status-item">
                {status.backend === 'ok' ? (
                    <CheckCircle size={16} className="icon success" />
                ) : (
                    <AlertCircle size={16} className="icon error" />
                )}
                <span className="label">Backend:</span>
                <span className="value">{status.backend}</span>
            </div>

            <div className="status-item">
                {status.uefn ? (
                    <CheckCircle size={16} className="icon success" />
                ) : (
                    <AlertCircle size={16} className="icon warning" />
                )}
                <span className="label">UEFN MCP:</span>
                <span className="value">
                    {status.uefn
                        ? `connected${status.uefnPort != null ? ` :${status.uefnPort}` : ''}`
                        : 'offline'}
                </span>
            </div>

            <div className="status-item">
                <Clock size={16} />
                <span className="value">{status.timestamp.toLocaleTimeString()}</span>
            </div>
        </footer>
    );
}

export default StatusBar;
