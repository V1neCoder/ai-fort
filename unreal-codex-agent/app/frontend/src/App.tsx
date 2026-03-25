import React, { useState, useEffect, useRef, useCallback, createContext, useContext } from 'react';
import { HashRouter as Router, Routes, Route, Link } from 'react-router-dom';
import axios from 'axios';
import {
    Menu, X, Settings, Zap, Package, Code,
    AlertCircle, CheckCircle, Download, WifiOff, MessageSquare
} from 'lucide-react';

import './App.css';
import ToolDashboard from './components/ToolDashboard';
import AssetBrowser from './components/AssetBrowser';
import CodexPanel from './components/CodexPanel';
import SettingsPanel from './components/SettingsPanel';
import ChatPanel from './components/ChatPanel';
import StatusBar from './components/StatusBar';

// Create context for backend URL
export const AppContext = createContext<{
    backendUrl: string;
    isConnected: boolean;
    appInfo: any;
}>({
    backendUrl: '',
    isConnected: false,
    appInfo: null
});

export const useAppContext = () => useContext(AppContext);

interface AppState {
    backendUrl: string;
    appInfo: any;
    isConnected: boolean;
    toolsLoaded: boolean;
    menuOpen: boolean;
    error: string | null;
    retryCount: number;
}

function App() {
    const retryRef = useRef(0);
    const [state, setState] = useState<AppState>({
        backendUrl: '',
        appInfo: null,
        isConnected: false,
        toolsLoaded: false,
        menuOpen: false,
        error: null,
        retryCount: 0
    });

    const initializeApp = useCallback(async () => {
        try {
            // Get backend URL from Electron or use default
            let backendUrl = 'http://127.0.0.1:8000';
            let appInfo = null;

            // Try to get URL from Electron API
            if ((window as any).electronAPI?.getBackendUrl) {
                const electronUrl = await (window as any).electronAPI.getBackendUrl();
                if (electronUrl) {
                    backendUrl = electronUrl;
                }
                console.log('Backend URL from Electron:', backendUrl);
            } else {
                console.log('Electron API not available, using default:', backendUrl);
            }

            // Try to get app info
            if ((window as any).electronAPI?.getAppInfo) {
                appInfo = await (window as any).electronAPI.getAppInfo();
            }

            // Test backend connection immediately
            console.log('Testing backend connection to:', backendUrl);
            const healthResponse = await axios.get(`${backendUrl}/api/health`, {
                timeout: 20000,
                headers: {
                    'Accept': 'application/json'
                }
            });

            console.log('Backend health check passed:', healthResponse.data);

            if (healthResponse.data?.features?.chat_sessions !== true) {
                throw new Error(
                    `Incompatible backend detected at ${backendUrl}. Stop old backend processes and restart the app.`
                );
            }

            retryRef.current = 0;
            setState(prev => ({
                ...prev,
                backendUrl,
                appInfo,
                isConnected: true,
                toolsLoaded: true,
                error: null,
                retryCount: 0
            }));
        } catch (error: any) {
            const errorMessage = error.message || 'Failed to connect to backend';
            console.error('App initialization failed:', errorMessage, error);

            retryRef.current += 1;
            const next = retryRef.current;
            setState(prev => ({
                ...prev,
                isConnected: false,
                error: `Backend connection failed: ${errorMessage}`,
                retryCount: next
            }));

            if (next < 3) {
                setTimeout(() => {
                    console.log('Retrying backend connection...');
                    void initializeApp();
                }, 3000);
            }
        }
    }, []);

    useEffect(() => {
        void initializeApp();
    }, [initializeApp]);

    const handleRetry = () => {
        retryRef.current = 0;
        setState(prev => ({ ...prev, retryCount: 0 }));
        void initializeApp();
    };

    // Show error screen if not connected and we've exhausted retries
    if (!state.isConnected && state.retryCount >= 3) {
        return (
            <div className="error-screen">
                <div className="error-content">
                    <WifiOff size={64} className="error-icon" />
                    <h2>Backend Connection Failed</h2>
                    <p>{state.error}</p>
                    <p className="error-details">
                        Make sure the current backend server is running and old copies are closed:
                    </p>
                    <code className="error-command">
                        cd "c:\AI Fort\unreal-codex-agent" && python app/backend/server.py
                    </code>
                    <button className="retry-button" onClick={handleRetry}>
                        Retry Connection
                    </button>
                </div>
            </div>
        );
    }

    // Show loading screen if connecting
    if (!state.isConnected) {
        return (
            <div className="loading-screen">
                <div className="loading-content">
                    <div className="loading-spinner"></div>
                    <h2>Connecting to Backend...</h2>
                    <p>Attempt {state.retryCount + 1}/3</p>
                </div>
            </div>
        );
    }

    return (
        <AppContext.Provider value={{
            backendUrl: state.backendUrl,
            isConnected: state.isConnected,
            appInfo: state.appInfo
        }}>
            <Router>
                <div className="app-container">
                    {/* Header */}
                    <header className="app-header">
                        <div className="header-content">
                            <div className="logo-section">
                                <Zap className="logo-icon" />
                                <h1>UEFN Codex Agent</h1>
                            </div>

                            {/* Navigation */}
                            <nav className={`nav-menu ${state.menuOpen ? 'open' : ''}`}>
                                <Link to="/" className="nav-link">
                                    <MessageSquare size={18} />
                                    Chat
                                </Link>
                                <Link to="/tools" className="nav-link">
                                    <Package size={18} />
                                    Tools
                                </Link>
                                <Link to="/assets" className="nav-link">
                                    <Download size={18} />
                                    Assets
                                </Link>
                                <Link to="/codex" className="nav-link">
                                    <Code size={18} />
                                    Codex
                                </Link>
                                <Link to="/settings" className="nav-link">
                                    <Settings size={18} />
                                    Settings
                                </Link>
                            </nav>

                            {/* Connection Status */}
                            <div className="status-indicator">
                                {state.isConnected ? (
                                    <>
                                        <CheckCircle size={16} className="status-icon connected" />
                                        <span>Connected</span>
                                    </>
                                ) : (
                                    <>
                                        <AlertCircle size={16} className="status-icon disconnected" />
                                        <span>Disconnected</span>
                                    </>
                                )}
                            </div>

                            {/* Mobile Menu Button */}
                            <button
                                className="menu-toggle"
                                onClick={() => setState(prev => ({ ...prev, menuOpen: !prev.menuOpen }))}
                            >
                                {state.menuOpen ? <X size={24} /> : <Menu size={24} />}
                            </button>
                        </div>
                    </header>

                    {/* Main Content */}
                    <main className="app-main">
                        <Routes>
                            <Route path="/" element={<ChatPanel backendUrl={state.backendUrl} />} />
                            <Route path="/tools" element={<ToolDashboard backendUrl={state.backendUrl} />} />
                            <Route path="/assets" element={<AssetBrowser backendUrl={state.backendUrl} />} />
                            <Route path="/codex" element={<CodexPanel backendUrl={state.backendUrl} />} />
                            <Route path="/settings" element={<SettingsPanel appInfo={state.appInfo} backendUrl={state.backendUrl} />} />
                        </Routes>
                    </main>

                    {/* Status Bar */}
                    <StatusBar backendUrl={state.backendUrl} isConnected={state.isConnected} />
                </div>
            </Router>
        </AppContext.Provider>
    );
}

export default App;
