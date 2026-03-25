import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
    Send, Plus, X, MessageSquare, Bot, User,
    FileText, Image as ImageIcon, AlertTriangle, Sparkles,
    BarChart3, ChevronDown, Check, Trash2, Pencil, RotateCcw,
    Search, FolderPlus, PanelLeft
} from 'lucide-react';
import axios from 'axios';
import '../styles/ChatPanel.css';

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    attachments?: AttachmentRecord[];
    toolResult?: { tool: string; output: any };
}

interface ChatSummary {
    id: string;
    title: string;
    project_id?: string;
    created_at: string;
    updated_at: string;
    message_count: number;
    preview: string;
    last_provider?: string;
    last_model?: string;
}

interface ChatSession {
    id: string;
    title: string;
    project_id?: string;
    created_at: string;
    updated_at: string;
    messages: ChatMessage[];
    memory_summary?: string;
    last_provider?: string;
    last_model?: string;
}

interface ProjectInfo {
    id: string;
    name: string;
    icon?: string;
    color?: string;
    created_at: string;
    updated_at: string;
    chat_count?: number;
}

interface AttachmentRecord {
    name: string;
    type: string;
    content?: string;
    mimeType?: string;
    sourceUrl?: string;
    size?: number;
    truncated?: boolean;
    analysisText?: string;
    analysisCaption?: string;
    analysisHandwriting?: string;
    analysisMeta?: Record<string, any>;
    analysisSummary?: string;
    analysisKeywords?: string[];
    analysisChunkCount?: number;
    attachmentFingerprint?: string;
}

interface AttachedFile extends AttachmentRecord {
    content: string;
}

interface UsageInfo {
    requests: number;
    tokens_in: number;
    tokens_out: number;
    tokens_total: number;
    limit_requests: number;
    limit_tokens: number;
    period: string;
    percent_used: number;
    label: string;
}

interface DialogState {
    title: string;
    message: string;
    mode: 'alert' | 'confirm';
    confirmLabel?: string;
    cancelLabel?: string;
    onConfirm?: (() => void) | null;
}

interface AttachmentViewerState {
    attachment: AttachmentRecord;
    origin: 'composer' | 'message';
}

const PROVIDER_MODELS: Record<string, { label: string; models: string[] }> = {
    groq: { label: 'Groq', models: ['llama-3.3-70b-versatile', 'deepseek-r1-distill-llama-70b', 'llama-3.1-8b-instant', 'gemma2-9b-it'] },
    cerebras: { label: 'Cerebras', models: ['qwen-3-235b-a22b-instruct-2507', 'llama3.1-8b'] },
    gemini: { label: 'Gemini', models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'] },
    ollama: { label: 'Ollama', models: [] },
};

const SUGGESTIONS = [
    "What actors are in my level?",
    "List all available tools",
    "Show project info",
    "Take a viewport screenshot",
    "Help me design a parkour course",
    "Color this red",
];

const CACHE_KEY_CHAT_STATUS = '_codex_ai_status';
const CACHE_KEY_MCP = '_codex_mcp_status';
const CACHE_KEY_ACTIVE_CHAT = '_codex_active_chat_id';
const CACHE_KEY_CHAT_DRAFT_PREFIX = '_codex_chat_draft_';
const MAX_TEXT_ATTACHMENT_CHARS = 750000;
const MAX_IMAGE_ATTACHMENT_BYTES = 12 * 1024 * 1024;
const TEXT_ATTACHMENT_EXTENSIONS = new Set([
    'txt', 'md', 'json', 'verse', 'py', 'js', 'jsx', 'ts', 'tsx',
    'css', 'html', 'htm', 'lua', 'ini', 'toml', 'yaml', 'yml', 'xml', 'csv', 'tsv',
    'mdx', 'svg', 'log', 'rst', 'sql', 'cfg', 'conf', 'env',
    'cpp', 'c', 'h', 'hpp', 'cs', 'java', 'go', 'rs', 'rb', 'php', 'sh', 'bat',
    'cmake', 'makefile', 'dockerfile', 'gitignore', 'editorconfig',
    'uproject', 'uplugin', 'uasset', 'umap',
]);

function cacheRead(key: string): any {
    try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : null; } catch { return null; }
}

function cacheWrite(key: string, data: any) {
    try { localStorage.setItem(key, JSON.stringify(data)); } catch { /* quota */ }
}

function chatDraftKey(chatId: string): string {
    return `${CACHE_KEY_CHAT_DRAFT_PREFIX}${chatId || 'new'}`;
}

function readDraft(chatId: string): string {
    try {
        return localStorage.getItem(chatDraftKey(chatId)) || '';
    } catch {
        return '';
    }
}

function writeDraft(chatId: string, value: string) {
    try {
        localStorage.setItem(chatDraftKey(chatId), value);
    } catch {
        // ignore quota errors
    }
}

function clearDraft(chatId: string) {
    try {
        localStorage.removeItem(chatDraftKey(chatId));
    } catch {
        // ignore quota errors
    }
}

function fileExtension(name: string): string {
    const parts = (name || '').toLowerCase().split('.');
    return parts.length > 1 ? parts[parts.length - 1] : '';
}

function isTextLikeFile(file: File): boolean {
    if (file.type.startsWith('text/')) return true;
    if (file.type === 'application/json') return true;
    if (file.type === 'application/xml' || file.type === 'image/svg+xml') return true;
    return TEXT_ATTACHMENT_EXTENSIONS.has(fileExtension(file.name));
}

function truncateText(value: string, limit: number): { text: string; truncated: boolean } {
    if (value.length <= limit) {
        return { text: value, truncated: false };
    }
    return { text: value.slice(0, limit), truncated: true };
}

function formatClock(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatSidebarTime(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    const now = new Date();
    const sameDay = date.toDateString() === now.toDateString();
    if (sameDay) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function compactText(text: string, limit = 90): string {
    const compact = (text || '').replace(/\s+/g, ' ').trim();
    if (compact.length <= limit) return compact;
    return `${compact.slice(0, limit - 1).trimEnd()}…`;
}

function summarizeChat(chat: ChatSession): ChatSummary {
    const lastMessage = chat.messages?.[chat.messages.length - 1];
    return {
        id: chat.id,
        title: chat.title || 'New Chat',
        project_id: chat.project_id || '',
        created_at: chat.created_at,
        updated_at: chat.updated_at,
        message_count: chat.messages?.length || 0,
        preview: compactText(lastMessage?.content || '', 96),
        last_provider: chat.last_provider,
        last_model: chat.last_model,
    };
}

function upsertChatSummary(list: ChatSummary[], summary: ChatSummary): ChatSummary[] {
    const next = [summary, ...list.filter(item => item.id !== summary.id)];
    return next.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));
}

function ChatPanel({ backendUrl }: { backendUrl: string }) {
    const cached = cacheRead(CACHE_KEY_CHAT_STATUS);
    const cachedMcp = cacheRead(CACHE_KEY_MCP);
    const cachedActiveChat = localStorage.getItem(CACHE_KEY_ACTIVE_CHAT) || '';

    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const [attachments, setAttachments] = useState<AttachedFile[]>([]);
    const [uefnConnected, setUefnConnected] = useState(cachedMcp?.connected || false);
    const [aiMode, setAiMode] = useState<'ai' | 'keyword' | 'unknown'>(
        cached?.ai_enabled ? 'ai' : cached ? 'keyword' : 'unknown'
    );
    const [aiProvider, setAiProvider] = useState(cached?.provider || '');

    const [usageOpen, setUsageOpen] = useState(false);
    const [usageData, setUsageData] = useState<Record<string, UsageInfo> | null>(null);
    const [usageDate, setUsageDate] = useState('');

    const [modelMenuOpen, setModelMenuOpen] = useState(false);
    const [availableProviders, setAvailableProviders] = useState<Record<string, any>>(cached?.available_providers || {});
    const [switchingModel, setSwitchingModel] = useState(false);

    const [chats, setChats] = useState<ChatSummary[]>([]);
    const [activeChatId, setActiveChatId] = useState(cachedActiveChat);
    const [activeChatTitle, setActiveChatTitle] = useState('New Chat');
    const [loadingChats, setLoadingChats] = useState(true);
    const [loadingChat, setLoadingChat] = useState(false);
    const [editingTitle, setEditingTitle] = useState(false);
    const [titleDraft, setTitleDraft] = useState('New Chat');
    const [savingChatMeta, setSavingChatMeta] = useState(false);
    const [showChatSearch, setShowChatSearch] = useState(false);
    const [chatSearchQuery, setChatSearchQuery] = useState('');
    const [dialog, setDialog] = useState<DialogState | null>(null);
    const [attachmentViewer, setAttachmentViewer] = useState<AttachmentViewerState | null>(null);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(localStorage.getItem('_codex_sidebar_collapsed') === 'true');
    const [isDraggingFiles, setIsDraggingFiles] = useState(false);

    // Project state
    const [projects, setProjects] = useState<ProjectInfo[]>([]);
    const [activeProjectId, setActiveProjectId] = useState<string>(localStorage.getItem('_codex_active_project') || '');
    const [editingProjectId, setEditingProjectId] = useState<string>('');
    const [projectNameDraft, setProjectNameDraft] = useState('');
    const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
    const [projectChatsMap, setProjectChatsMap] = useState<Record<string, ChatSummary[]>>({});
    const [iconPickerProjectId, setIconPickerProjectId] = useState<string>('');
    const [colorPickerProjectId, setColorPickerProjectId] = useState<string>('');
    const [renamingChatId, setRenamingChatId] = useState<string>('');
    const [renamingChatDraft, setRenamingChatDraft] = useState<string>('');

    const PROJECT_ICONS = [
        '📁', '🎮', '🏗️', '🎯', '🎨', '⚡', '🔥', '💎', '🚀', '🌍',
        '🏰', '🗡️', '🛡️', '🎪', '🎭', '🌟', '💫', '🔮', '🎲', '🏆',
        '🌈', '🍀', '🐉', '👾', '🤖', '🎵', '🔧', '📦', '🧩', '💡',
        '🦊', '🐺', '🦅', '🐙', '🌺', '🍄', '⭐', '☀️', '🌙', '❄️',
    ];

    const PROJECT_COLORS = [
        '', '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4',
        '#3b82f6', '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
        '#14b8a6', '#84cc16', '#a855f7',
    ];

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const modelMenuRef = useRef<HTMLDivElement>(null);
    const chatSearchInputRef = useRef<HTMLInputElement>(null);
    const dragDepthRef = useRef(0);

    const autoResize = useCallback(() => {
        const el = textareaRef.current;
        if (el) {
            el.style.height = 'auto';
            el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
        }
    }, []);

    const refreshRuntimeStatus = useCallback(async () => {
        try {
            const mcpResponse = await axios.get(`${backendUrl}/api/uefn/mcp/status`);
            setUefnConnected(mcpResponse.data?.connected || false);
            cacheWrite(CACHE_KEY_MCP, mcpResponse.data);
        } catch {
            // keep cached state
        }

        try {
            const statusResponse = await axios.get(`${backendUrl}/api/chat/status`);
            const data = statusResponse.data;
            if (data?.ai_enabled) {
                setAiMode('ai');
                setAiProvider(data?.provider || 'ai');
            } else {
                setAiMode('keyword');
            }
            setAvailableProviders(data?.available_providers || {});
            cacheWrite(CACHE_KEY_CHAT_STATUS, data);
        } catch {
            // keep cached state
        }
    }, [backendUrl]);

    /* eslint-disable react-hooks/exhaustive-deps */
    // Bootstrap runtime status and the active stored chat whenever the backend target changes.
    useEffect(() => {
        void refreshRuntimeStatus();
        void loadProjects();
        void loadChatList(cachedActiveChat);
    }, [backendUrl]);
    /* eslint-enable react-hooks/exhaustive-deps */

    useEffect(() => {
        function handleFocus() {
            void refreshRuntimeStatus();
        }

        function handleVisibility() {
            if (!document.hidden) {
                void refreshRuntimeStatus();
            }
        }

        window.addEventListener('focus', handleFocus);
        document.addEventListener('visibilitychange', handleVisibility);
        return () => {
            window.removeEventListener('focus', handleFocus);
            document.removeEventListener('visibilitychange', handleVisibility);
        };
    }, [refreshRuntimeStatus]);

    useEffect(() => {
        setEditingTitle(false);
        setTitleDraft(activeChatTitle || 'New Chat');
    }, [activeChatTitle]);

    useEffect(() => {
        const draft = readDraft(activeChatId);
        setInput(draft);
        requestAnimationFrame(() => autoResize());
    }, [activeChatId, autoResize]);

    useEffect(() => {
        if (showChatSearch) {
            requestAnimationFrame(() => chatSearchInputRef.current?.focus());
        }
    }, [showChatSearch]);

    async function loadUsage() {
        try {
            const response = await axios.get(`${backendUrl}/api/chat/usage`);
            setUsageData(response.data?.providers || null);
            setUsageDate(response.data?.date || '');
        } catch {
            setUsageData(null);
        }
    }

    // ── Project functions ──
    async function loadProjects() {
        try {
            const res = await axios.get(`${backendUrl}/api/projects`);
            setProjects(res.data?.projects || []);
        } catch { /* keep existing */ }
    }

    async function createProject() {
        try {
            const res = await axios.post(`${backendUrl}/api/projects`, { name: 'New project', icon: '📁' });
            const proj: ProjectInfo = res.data?.project;
            setProjects(prev => [proj, ...prev]);
            setEditingProjectId(proj.id);
            setProjectNameDraft(proj.name);
            // Auto-expand and create first chat
            setExpandedProjects(prev => new Set([...prev, proj.id]));
            const created = await createChat(true, proj.id);
            if (created) {
                setProjectChatsMap(prev => ({ ...prev, [proj.id]: [summarizeChat(created)] }));
                setActiveProjectId(proj.id);
                localStorage.setItem('_codex_active_project', proj.id);
            }
        } catch (e: any) {
            console.error('Failed to create project:', e);
        }
    }

    async function renameProject(projectId: string, name: string) {
        try {
            const res = await axios.patch(`${backendUrl}/api/projects/${projectId}`, { name });
            const updated = res.data?.project;
            setProjects(prev => prev.map(p => p.id === projectId ? { ...p, ...updated } : p));
            setEditingProjectId('');
        } catch { /* ignore */ }
    }

    async function updateProjectIcon(projectId: string, icon: string) {
        try {
            const res = await axios.patch(`${backendUrl}/api/projects/${projectId}`, { icon });
            const updated = res.data?.project;
            setProjects(prev => prev.map(p => p.id === projectId ? { ...p, ...updated } : p));
            setIconPickerProjectId('');
        } catch { /* ignore */ }
    }

    async function updateProjectColor(projectId: string, color: string) {
        try {
            const res = await axios.patch(`${backendUrl}/api/projects/${projectId}`, { color });
            const updated = res.data?.project;
            setProjects(prev => prev.map(p => p.id === projectId ? { ...p, ...updated } : p));
            setColorPickerProjectId('');
        } catch { /* ignore */ }
    }

    async function deleteProject(projectId: string) {
        setDialog({
            title: 'Delete Project',
            message: 'Delete this project and all its chats? This cannot be undone.',
            mode: 'confirm',
            confirmLabel: 'Delete',
            cancelLabel: 'Cancel',
            onConfirm: async () => {
                try {
                    await axios.delete(`${backendUrl}/api/projects/${projectId}`);
                    setProjects(prev => prev.filter(p => p.id !== projectId));
                    setProjectChatsMap(prev => { const n = { ...prev }; delete n[projectId]; return n; });
                    if (activeProjectId === projectId) {
                        setActiveProjectId('');
                        localStorage.removeItem('_codex_active_project');
                        await loadChatList();
                    }
                } catch { /* ignore */ }
            },
        });
    }

    async function toggleProjectExpand(projectId: string) {
        const isExpanded = expandedProjects.has(projectId);
        if (isExpanded) {
            setExpandedProjects(prev => { const n = new Set(prev); n.delete(projectId); return n; });
        } else {
            setExpandedProjects(prev => new Set([...prev, projectId]));
            // Load chats for this project if not loaded
            if (!projectChatsMap[projectId]) {
                try {
                    const res = await axios.get(`${backendUrl}/api/chats?project_id=${projectId}`);
                    setProjectChatsMap(prev => ({ ...prev, [projectId]: res.data?.chats || [] }));
                } catch { /* ignore */ }
            }
        }
    }

    async function renameChat(chatId: string, newTitle: string, projectId?: string) {
        const title = newTitle.trim() || 'New Chat';
        try {
            const res = await axios.patch(`${backendUrl}/api/chats/${chatId}`, { title });
            const chat: ChatSession = res.data?.chat;
            const summary = summarizeChat(chat);
            setChats(prev => upsertChatSummary(prev, summary));
            if (projectId) {
                setProjectChatsMap(prev => ({
                    ...prev,
                    [projectId]: (prev[projectId] || []).map(c => c.id === chatId ? { ...c, title: chat.title || title } : c),
                }));
            }
            if (activeChatId === chatId) {
                setActiveChatTitle(chat.title || title);
            }
        } catch { /* ignore */ }
        setRenamingChatId('');
    }

    function selectProjectChat(projectId: string, chatId: string) {
        setActiveProjectId(projectId);
        localStorage.setItem('_codex_active_project', projectId);
        void selectChat(chatId);
    }

    async function newChatInProject(projectId: string) {
        const created = await createChat(true, projectId);
        if (created) {
            setActiveProjectId(projectId);
            localStorage.setItem('_codex_active_project', projectId);
            const summary = summarizeChat(created);
            setProjectChatsMap(prev => ({
                ...prev,
                [projectId]: [summary, ...(prev[projectId] || [])],
            }));
            setExpandedProjects(prev => new Set([...prev, projectId]));
        }
    }

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    function exitProject() {
        setActiveProjectId('');
        localStorage.removeItem('_codex_active_project');
        loadChatList();
    }

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    async function loadChatListForProject(projectId: string) {
        setLoadingChats(true);
        try {
            const response = await axios.get(`${backendUrl}/api/chats?project_id=${projectId}`);
            const items: ChatSummary[] = response.data?.chats || [];
            setChats(items);
            setProjectChatsMap(prev => ({ ...prev, [projectId]: items }));
            if (items.length > 0) {
                await selectChat(items[0].id, items);
            } else {
                const created = await createChat(true, projectId);
                if (created) {
                    const summary = summarizeChat(created);
                    setChats([summary]);
                    setProjectChatsMap(prev => ({ ...prev, [projectId]: [summary] }));
                    setMessages(created.messages || []);
                }
            }
        } catch (error) {
            console.error('Failed to load project chats:', error);
        } finally {
            setLoadingChats(false);
        }
    }

    async function loadChatList(preferredChatId?: string) {
        setLoadingChats(true);
        try {
            // Load ALL chats
            const response = await axios.get(`${backendUrl}/api/chats`);
            const allItems: ChatSummary[] = response.data?.chats || [];
            setChats(allItems);

            // Standalone chats (no project)
            const standalone = allItems.filter(c => !c.project_id);

            if (standalone.length === 0 && !activeProjectId) {
                const created = await createChat(true, '');
                if (created) {
                    const summary = summarizeChat(created);
                    setChats(prev => [summary, ...prev]);
                    setMessages(created.messages || []);
                    setActiveChatTitle(created.title || 'New Chat');
                }
                return;
            }

            const rememberedId = preferredChatId || activeChatId || localStorage.getItem(CACHE_KEY_ACTIVE_CHAT) || '';
            const allChatIds = allItems.map(c => c.id);
            const nextChatId = allChatIds.includes(rememberedId)
                ? rememberedId
                : (standalone.length > 0 ? standalone[0].id : allItems[0]?.id || '');
            if (nextChatId) {
                await selectChat(nextChatId, allItems);
            }
        } catch (error) {
            console.error('Failed to load chats:', error);
        } finally {
            setLoadingChats(false);
        }
    }

    async function createChat(selectAfterCreate = true, projectId?: string): Promise<ChatSession | null> {
        try {
            const response = await axios.post(`${backendUrl}/api/chats`, {
                title: '',
                project_id: projectId !== undefined ? projectId : activeProjectId || '',
            });
            const chat: ChatSession = response.data?.chat;
            const summary = summarizeChat(chat);
            setChats(prev => upsertChatSummary(prev, summary));
            if (selectAfterCreate) {
                setEditingTitle(false);
                setActiveChatId(chat.id);
                setActiveChatTitle(chat.title || 'New Chat');
                setMessages(chat.messages || []);
                localStorage.setItem(CACHE_KEY_ACTIVE_CHAT, chat.id);
            }
            return chat;
        } catch (error: any) {
            console.error('Failed to create chat:', error);
            setDialog({
                title: 'uefn-codex-electron',
                message: error?.response?.data?.error || 'Failed to create a new chat',
                mode: 'alert',
                confirmLabel: 'OK',
            });
            return null;
        }
    }

    async function selectChat(chatId: string, knownChats?: ChatSummary[]) {
        if (!chatId) return;
        setActiveChatId(chatId);
        localStorage.setItem(CACHE_KEY_ACTIVE_CHAT, chatId);
        const matchingChat = (knownChats || chats).find(item => item.id === chatId);
        setActiveChatTitle(matchingChat?.title || 'New Chat');
        setEditingTitle(false);
        setLoadingChat(true);
        try {
            const response = await axios.get(`${backendUrl}/api/chats/${chatId}`);
            const chat: ChatSession = response.data?.chat;
            setMessages(chat?.messages || []);
            setActiveChatTitle(chat?.title || 'New Chat');
            setChats(prev => upsertChatSummary(prev, summarizeChat(chat)));
        } catch (error) {
            console.error('Failed to load chat:', error);
        } finally {
            setLoadingChat(false);
        }
    }

    async function deleteChat(chatId: string) {
        try {
            await axios.delete(`${backendUrl}/api/chats/${chatId}`);
            clearDraft(chatId);
            const remaining = chats.filter(chat => chat.id !== chatId);
            setChats(remaining);

            if (activeChatId === chatId) {
                if (remaining.length > 0) {
                    await selectChat(remaining[0].id, remaining);
                } else {
                    const created = await createChat(true);
                    if (created) {
                        setChats([summarizeChat(created)]);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to delete chat:', error);
        }
    }

    async function renameActiveChat() {
        if (!activeChatId || savingChatMeta) return;
        const nextTitle = titleDraft.trim() || 'New Chat';
        setSavingChatMeta(true);
        try {
            const response = await axios.patch(`${backendUrl}/api/chats/${activeChatId}`, {
                title: nextTitle,
            });
            const chat: ChatSession = response.data?.chat;
            setActiveChatTitle(chat.title || 'New Chat');
            setChats(prev => upsertChatSummary(prev, summarizeChat(chat)));
            setEditingTitle(false);
        } catch (error: any) {
            console.error('Failed to rename chat:', error);
            setDialog({
                title: 'uefn-codex-electron',
                message: error?.response?.data?.error || 'Failed to rename chat',
                mode: 'alert',
                confirmLabel: 'OK',
            });
        } finally {
            setSavingChatMeta(false);
        }
    }

    async function performClearActiveChat() {
        if (!activeChatId || savingChatMeta) return;

        setSavingChatMeta(true);
        try {
            const response = await axios.patch(`${backendUrl}/api/chats/${activeChatId}`, {
                clear_messages: true,
            });
            const chat: ChatSession = response.data?.chat;
            setMessages(chat.messages || []);
            setActiveChatTitle(chat.title || 'New Chat');
            setChats(prev => upsertChatSummary(prev, summarizeChat(chat)));
        } catch (error: any) {
            console.error('Failed to clear chat:', error);
            setDialog({
                title: 'uefn-codex-electron',
                message: error?.response?.data?.error || 'Failed to clear chat',
                mode: 'alert',
                confirmLabel: 'OK',
            });
        } finally {
            setSavingChatMeta(false);
        }
    }

    function clearActiveChat() {
        if (!activeChatId || savingChatMeta) return;
        setDialog({
            title: 'uefn-codex-electron',
            message: 'Clear this project chat history and reset its memory?',
            mode: 'confirm',
            confirmLabel: 'Clear',
            cancelLabel: 'Cancel',
            onConfirm: () => { void performClearActiveChat(); },
        });
    }

    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (modelMenuOpen && modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
                setModelMenuOpen(false);
            }
        }
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [modelMenuOpen]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, sending]);

    function handleInputChange(value: string) {
        setInput(value);
        writeDraft(activeChatId, value);
        requestAnimationFrame(() => autoResize());
    }

    function queueAttachment(next: AttachedFile) {
        setAttachments(prev => {
            const duplicate = prev.some(existing =>
                existing.name === next.name
                && existing.type === next.type
                && existing.size === next.size
                && existing.content === next.content
            );
            if (duplicate) {
                return prev;
            }
            return [...prev, next];
        });
    }

    function openAttachmentViewer(attachment: AttachmentRecord, origin: 'composer' | 'message') {
        if (!attachment.content) {
            setDialog({
                title: 'uefn-codex-electron',
                message: 'Preview is unavailable for this attachment.',
                mode: 'alert',
                confirmLabel: 'OK',
            });
            return;
        }
        setAttachmentViewer({ attachment, origin });
    }

    function renderAttachmentInsights(attachment: AttachmentRecord) {
        const summary = (attachment.analysisSummary || '').trim();
        const caption = (attachment.analysisCaption || '').trim();
        const handwriting = (attachment.analysisHandwriting || '').trim();
        const keywords = (attachment.analysisKeywords || []).filter(Boolean);
        const text = (attachment.analysisText || '').trim();
        const metaEntries = Object.entries(attachment.analysisMeta || {}).filter(([, value]) => value !== undefined && value !== null && value !== '');
        const chunkCount = Math.max(0, Number(attachment.analysisChunkCount || 0));
        const textLabel = attachment.type === 'image' ? 'Detected text' : 'Extracted content';

        if (!summary && !caption && !handwriting && keywords.length === 0 && !text && metaEntries.length === 0) {
            return null;
        }

        return (
            <div className="attachment-analysis-block">
                {summary && (
                    <>
                        <div className="attachment-analysis-label">Summary</div>
                        <div className="attachment-analysis-summary">{summary}</div>
                    </>
                )}
                {caption && (
                    <>
                        <div className="attachment-analysis-label">Visual description</div>
                        <div className="attachment-analysis-summary">{caption}</div>
                    </>
                )}
                {handwriting && (
                    <>
                        <div className="attachment-analysis-label">Handwriting guess</div>
                        <pre className="attachment-viewer-text attachment-analysis-text">
                            {handwriting}
                        </pre>
                    </>
                )}
                {metaEntries.length > 0 && (
                    <>
                        <div className="attachment-analysis-label">Visual diagnostics</div>
                        <pre className="attachment-viewer-text attachment-analysis-text">
                            {JSON.stringify(attachment.analysisMeta, null, 2)}
                        </pre>
                    </>
                )}
                {keywords.length > 0 && (
                    <>
                        <div className="attachment-analysis-label">Keywords</div>
                        <div className="attachment-analysis-keywords">
                            {keywords.map(keyword => (
                                <span key={keyword} className="attachment-analysis-chip">
                                    {keyword}
                                </span>
                            ))}
                        </div>
                    </>
                )}
                {chunkCount > 1 && (
                    <>
                        <div className="attachment-analysis-label">Compiled sections</div>
                        <div className="attachment-analysis-summary">{chunkCount} sections indexed for retrieval</div>
                    </>
                )}
                {text && (
                    <>
                        <div className="attachment-analysis-label">{textLabel}</div>
                        <pre className="attachment-viewer-text attachment-analysis-text">
                            {text}
                        </pre>
                    </>
                )}
            </div>
        );
    }

    function readFileAsText(file: File): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
            reader.onload = () => resolve(String(reader.result || ''));
            reader.readAsText(file);
        });
    }

    function readFileAsDataUrl(file: File): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
            reader.onload = () => resolve(String(reader.result || ''));
            reader.readAsDataURL(file);
        });
    }

    async function addFile(file: File) {
        const isImage = file.type.startsWith('image/');
        try {
            if (isImage) {
                if (file.size > MAX_IMAGE_ATTACHMENT_BYTES) {
                    setDialog({
                        title: 'uefn-codex-electron',
                        message: `${file.name} is too large. Keep pasted/imported images under 12 MB.`,
                        mode: 'alert',
                        confirmLabel: 'OK',
                    });
                    return;
                }

                const content = await readFileAsDataUrl(file);
                queueAttachment({
                    name: file.name || `image-${Date.now()}.png`,
                    type: 'image',
                    mimeType: file.type || 'image/png',
                    size: file.size,
                    content,
                });
                return;
            }

            if (isTextLikeFile(file)) {
                const text = await readFileAsText(file);
                const truncated = truncateText(text, MAX_TEXT_ATTACHMENT_CHARS);
                queueAttachment({
                    name: file.name,
                    type: 'file',
                    mimeType: file.type || 'text/plain',
                    size: file.size,
                    content: truncated.text,
                    truncated: truncated.truncated,
                });
                return;
            }

            const content = await readFileAsDataUrl(file);
            queueAttachment({
                name: file.name,
                type: 'binary',
                mimeType: file.type || 'application/octet-stream',
                size: file.size,
                content,
            });
        } catch (error: any) {
            console.error('Failed to add attachment:', error);
            setDialog({
                title: 'uefn-codex-electron',
                message: error?.message || `Failed to import ${file.name}`,
                mode: 'alert',
                confirmLabel: 'OK',
            });
        }
    }

    function removeAttachment(idx: number) {
        setAttachments(prev => prev.filter((_, i) => i !== idx));
    }

    function hasFiles(dataTransfer?: DataTransfer | null): boolean {
        if (!dataTransfer) return false;
        return Array.from(dataTransfer.types || []).includes('Files');
    }

    function enqueueFiles(fileList: FileList | File[]) {
        Array.from(fileList || []).forEach(file => {
            void addFile(file);
        });
    }

    function handleComposerPaste(e: React.ClipboardEvent<HTMLTextAreaElement>) {
        const files = Array.from(e.clipboardData.items || [])
            .filter(item => item.kind === 'file')
            .map(item => item.getAsFile())
            .filter((file): file is File => Boolean(file));

        if (files.length === 0) {
            return;
        }

        e.preventDefault();
        enqueueFiles(files);
    }

    function handleDragEnter(e: React.DragEvent) {
        if (!hasFiles(e.dataTransfer)) return;
        e.preventDefault();
        e.stopPropagation();
        dragDepthRef.current += 1;
        setIsDraggingFiles(true);
    }

    function handleDragOver(e: React.DragEvent) {
        if (!hasFiles(e.dataTransfer)) return;
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'copy';
        if (!isDraggingFiles) {
            setIsDraggingFiles(true);
        }
    }

    function handleDragLeave(e: React.DragEvent) {
        if (!hasFiles(e.dataTransfer)) return;
        e.preventDefault();
        e.stopPropagation();
        dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
        if (dragDepthRef.current === 0) {
            setIsDraggingFiles(false);
        }
    }

    function handleDrop(e: React.DragEvent) {
        if (!hasFiles(e.dataTransfer)) return;
        e.preventDefault();
        e.stopPropagation();
        dragDepthRef.current = 0;
        setIsDraggingFiles(false);
        if (e.dataTransfer.files?.length) {
            enqueueFiles(e.dataTransfer.files);
        }
    }

    function formatToolOutput(output: any): string {
        if (output === undefined || output === null) return String(output ?? '(no output)');
        if (typeof output === 'string') {
            return output.replace(/data:[^;]+;base64,[A-Za-z0-9+/=]{100,}/g, '[binary data]');
        }
        const str = JSON.stringify(output, null, 2) || '(empty)';
        return str.replace(/"data:[^;]+;base64,[A-Za-z0-9+/=]{100,}"/g, '"[binary data]"');
    }

    function renderContent(text: string) {
        const parts = text.split(/(```[\s\S]*?```)/g);
        return parts.map((part, i) => {
            if (part.startsWith('```') && part.endsWith('```')) {
                const code = part.slice(3, -3).replace(/^\w+\n/, '');
                return <pre key={i} className="msg-code-block">{code}</pre>;
            }
            const lines = part.split('\n');
            return (
                <span key={i}>
                    {lines.map((line, j) => (
                        <React.Fragment key={j}>
                            {j > 0 && <br />}
                            {renderLine(line)}
                        </React.Fragment>
                    ))}
                </span>
            );
        });
    }

    function renderLine(line: string) {
        const parts = line.split(/(\*\*.*?\*\*)/g);
        return parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={i}>{part.slice(2, -2)}</strong>;
            }
            const codeParts = part.split(/(`[^`]+`)/g);
            return codeParts.map((cp, j) => {
                if (cp.startsWith('`') && cp.endsWith('`')) {
                    return <code key={`${i}-${j}`} className="msg-inline-code">{cp.slice(1, -1)}</code>;
                }
                return <span key={`${i}-${j}`}>{cp}</span>;
            });
        });
    }

    async function switchModel(provider: string, model?: string) {
        setSwitchingModel(true);
        try {
            const payload: any = { provider };
            if (model) payload.model = model;
            const response = await axios.post(`${backendUrl}/api/chat/model`, payload);
            setAiProvider(response.data?.provider || provider);
            setModelMenuOpen(false);
            await refreshRuntimeStatus();
        } catch (error: any) {
            console.error('Model switch failed:', error);
            setDialog({
                title: 'uefn-codex-electron',
                message: error?.response?.data?.error || 'Model switch failed',
                mode: 'alert',
                confirmLabel: 'OK',
            });
        } finally {
            setSwitchingModel(false);
        }
    }

    async function sendMessage(text?: string) {
        const msgText = (text || input).trim();
        if (!msgText && attachments.length === 0) return;

        let chatId = activeChatId;
        const pendingAttachments = attachments;
        let userMsg: ChatMessage | null = null;

        try {
            if (!chatId) {
                const created = await createChat(true);
                if (!created) return;
                chatId = created.id;
            }

            userMsg = {
                id: `u-${Date.now()}`,
                role: 'user',
                content: msgText || `Shared attachments: ${attachments.map(file => file.name).join(', ')}`,
                timestamp: new Date().toISOString(),
                attachments: attachments.map(file => ({
                    name: file.name,
                    type: file.type,
                    mimeType: file.mimeType,
                    sourceUrl: file.sourceUrl,
                    size: file.size,
                    truncated: file.truncated,
                    analysisText: file.analysisText,
                    analysisCaption: file.analysisCaption,
                    analysisHandwriting: file.analysisHandwriting,
                    analysisMeta: file.analysisMeta,
                    analysisSummary: file.analysisSummary,
                    analysisKeywords: file.analysisKeywords,
                    content: file.content,
                })),
            };

            setMessages(prev => [...prev, userMsg]);
            setInput('');
            setAttachments([]);
            setSending(true);
            if (textareaRef.current) textareaRef.current.style.height = 'auto';

            const response = await axios.post(`${backendUrl}/api/chat`, {
                chat_id: chatId,
                message: msgText,
                attachments: attachments.map(file => ({
                    name: file.name,
                    type: file.type,
                    mime_type: file.mimeType,
                    source_url: file.sourceUrl,
                    size: file.size,
                    truncated: Boolean(file.truncated),
                    analysis_text: file.analysisText,
                    analysis_caption: file.analysisCaption,
                    analysis_handwriting: file.analysisHandwriting,
                    analysis_meta: file.analysisMeta,
                    analysis_summary: file.analysisSummary,
                    analysis_keywords: file.analysisKeywords,
                    content: file.content,
                })),
            }, { timeout: 120000 });

            const data = response.data;
            if (data?.chat?.messages) {
                setMessages(data.chat.messages);
                setActiveChatTitle(data.chat.title || 'New Chat');
                setChats(prev => upsertChatSummary(prev, summarizeChat(data.chat)));
            } else {
                const assistantMsg: ChatMessage = {
                    id: `a-${Date.now()}`,
                    role: 'assistant',
                    content: data.reply || data.message || 'No response',
                    timestamp: new Date().toISOString(),
                    toolResult: data.tool_result,
                };
                setMessages(prev => [...prev, assistantMsg]);
            }

            if (data?.chat_id) {
                setActiveChatId(data.chat_id);
                localStorage.setItem(CACHE_KEY_ACTIVE_CHAT, data.chat_id);
            }

            clearDraft(chatId);

            if (aiMode === 'keyword') {
                await refreshRuntimeStatus();
            }
        } catch (err: any) {
            if (userMsg) {
                setMessages(prev => prev.filter(message => message.id !== userMsg.id));
            }
            setInput(msgText);
            setAttachments(pendingAttachments);
            writeDraft(chatId, msgText);
            requestAnimationFrame(() => autoResize());
            const errMsg: ChatMessage = {
                id: `e-${Date.now()}`,
                role: 'assistant',
                content: `Error: ${err?.response?.data?.error || err?.message || 'Failed to reach backend'}`,
                timestamp: new Date().toISOString(),
            };
            setMessages(prev => [...prev, errMsg]);
        } finally {
            setSending(false);
        }
    }

    function handleKeyDown(e: React.KeyboardEvent) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            void sendMessage();
        }
    }

    function toggleUsage() {
        if (!usageOpen) void loadUsage();
        setUsageOpen(!usageOpen);
    }

    function formatNumber(n: number): string {
        if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
        if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
        return String(n);
    }

    function getBarColor(pct: number): string {
        if (pct >= 90) return '#ef4444';
        if (pct >= 70) return '#f59e0b';
        return '#22c55e';
    }

    const providerLabel = PROVIDER_MODELS[aiProvider]?.label || aiProvider || 'AI';
    const filteredChats = useMemo(() => {
        const query = chatSearchQuery.trim().toLowerCase();
        // Only show standalone (non-project) chats in "Your chats"
        let items = chats.filter(c => !c.project_id);
        if (query) {
            items = items.filter(chat =>
                chat.title.toLowerCase().includes(query) ||
                (chat.preview || '').toLowerCase().includes(query)
            );
        }
        return items;
    }, [chatSearchQuery, chats]);

    const switcherProviders: { prov: string; label: string }[] = [];
    for (const prov of ['groq', 'cerebras', 'gemini', 'ollama']) {
        const backend = availableProviders[prov];
        const stat = PROVIDER_MODELS[prov];
        const hasKey = backend?.has_key || false;
        const isOllama = prov === 'ollama';
        const isAvailable = backend?.is_available ?? (hasKey || (isOllama && backend?.models?.length > 0));

        if (isAvailable) {
            switcherProviders.push({ prov, label: stat?.label || prov });
        }
    }

    return (
        <div
            className={`chat-panel ${isDraggingFiles ? 'drag-active' : ''}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {isDraggingFiles && (
                <div className="chat-file-drop-overlay" aria-hidden="true">
                    <div className="chat-file-drop-card">
                        <strong>Drop files to attach</strong>
                        <span>Images, screenshots, docs, and code files will be added to this chat.</span>
                    </div>
                </div>
            )}
            {dialog && (
                <div className="chat-dialog-backdrop" onClick={() => setDialog(null)}>
                    <div className="chat-dialog-window" onClick={(e) => e.stopPropagation()}>
                        <div className="chat-dialog-titlebar">
                            <span>{dialog.title}</span>
                            <button type="button" className="chat-dialog-close" onClick={() => setDialog(null)} aria-label="Close dialog">
                                <X size={16} />
                            </button>
                        </div>
                        <div className="chat-dialog-body">
                            <p>{dialog.message}</p>
                        </div>
                        <div className="chat-dialog-footer">
                            {dialog.mode === 'confirm' && (
                                <button type="button" className="chat-dialog-btn secondary" onClick={() => setDialog(null)}>
                                    {dialog.cancelLabel || 'Cancel'}
                                </button>
                            )}
                            <button
                                type="button"
                                className="chat-dialog-btn primary"
                                onClick={() => {
                                    const action = dialog.onConfirm;
                                    setDialog(null);
                                    action?.();
                                }}
                            >
                                {dialog.confirmLabel || 'OK'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {attachmentViewer && (
                <div className="chat-dialog-backdrop attachment-viewer-backdrop" onClick={() => setAttachmentViewer(null)}>
                    <div className="attachment-viewer-window" onClick={(e) => e.stopPropagation()}>
                        <div className="chat-dialog-titlebar attachment-viewer-titlebar">
                            <div className="attachment-viewer-title-copy">
                                <span>{attachmentViewer.attachment.name}</span>
                                <small>
                                    {attachmentViewer.attachment.type}
                                    {attachmentViewer.attachment.mimeType ? ` • ${attachmentViewer.attachment.mimeType}` : ''}
                                    {attachmentViewer.attachment.size ? ` • ${Math.max(1, Math.round(attachmentViewer.attachment.size / 1024))} KB` : ''}
                                </small>
                                {attachmentViewer.attachment.sourceUrl && (
                                    <a
                                        className="attachment-viewer-source"
                                        href={attachmentViewer.attachment.sourceUrl}
                                        target="_blank"
                                        rel="noreferrer"
                                    >
                                        {attachmentViewer.attachment.sourceUrl}
                                    </a>
                                )}
                            </div>
                            <button type="button" className="chat-dialog-close" onClick={() => setAttachmentViewer(null)} aria-label="Close attachment viewer">
                                <X size={16} />
                            </button>
                        </div>
                        <div className="attachment-viewer-body">
                            {attachmentViewer.attachment.type === 'image' && attachmentViewer.attachment.content ? (
                                <div className="attachment-viewer-stack">
                                    <img
                                        src={attachmentViewer.attachment.content}
                                        alt={attachmentViewer.attachment.name}
                                        className="attachment-viewer-image"
                                    />
                                    {renderAttachmentInsights(attachmentViewer.attachment)}
                                </div>
                            ) : attachmentViewer.attachment.type === 'binary' ? (
                                attachmentViewer.attachment.analysisText || attachmentViewer.attachment.analysisSummary || (attachmentViewer.attachment.analysisKeywords || []).length > 0 ? (
                                    <div className="attachment-viewer-stack">
                                        {renderAttachmentInsights(attachmentViewer.attachment)}
                                        {attachmentViewer.attachment.content && (
                                            <a
                                                className="attachment-viewer-download"
                                                href={attachmentViewer.attachment.content}
                                                download={attachmentViewer.attachment.name}
                                            >
                                                Download copy
                                            </a>
                                        )}
                                    </div>
                                ) : (
                                    <div className="attachment-viewer-empty">
                                        <p>This file was imported and attached, but it is binary so there is no inline text preview.</p>
                                        {attachmentViewer.attachment.content && (
                                            <a
                                                className="attachment-viewer-download"
                                                href={attachmentViewer.attachment.content}
                                                download={attachmentViewer.attachment.name}
                                            >
                                                Download copy
                                            </a>
                                        )}
                                    </div>
                                )
                            ) : (
                                <div className="attachment-viewer-stack">
                                    <pre className="attachment-viewer-text">
                                        {attachmentViewer.attachment.content || 'No preview content stored.'}
                                    </pre>
                                    {renderAttachmentInsights(attachmentViewer.attachment)}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            <div className="chat-header">
                <div className="chat-header-left">
                    <MessageSquare size={22} className="chat-icon" />
                    <div className="chat-title-stack">
                        <h2>AI Assistant</h2>
                        <div className="chat-project-row">
                            {editingTitle ? (
                                <>
                                    <input
                                        type="text"
                                        className="chat-project-input"
                                        value={titleDraft}
                                        onChange={(e) => setTitleDraft(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                e.preventDefault();
                                                void renameActiveChat();
                                            }
                                            if (e.key === 'Escape') {
                                                setEditingTitle(false);
                                                setTitleDraft(activeChatTitle || 'New Chat');
                                            }
                                        }}
                                        disabled={savingChatMeta}
                                    />
                                    <button
                                        type="button"
                                        className="chat-project-action save"
                                        onClick={() => void renameActiveChat()}
                                        disabled={savingChatMeta}
                                    >
                                        Save
                                    </button>
                                    <button
                                        type="button"
                                        className="chat-project-action"
                                        onClick={() => {
                                            setEditingTitle(false);
                                            setTitleDraft(activeChatTitle || 'New Chat');
                                        }}
                                        disabled={savingChatMeta}
                                    >
                                        Cancel
                                    </button>
                                </>
                            ) : (
                                <>
                                    <span className="chat-project-label">{activeChatTitle}</span>
                                    <button
                                        type="button"
                                        className="chat-project-icon"
                                        onClick={() => {
                                            setEditingTitle(true);
                                            setTitleDraft(activeChatTitle || 'New Chat');
                                        }}
                                        disabled={!activeChatId || savingChatMeta}
                                        title="Rename project"
                                    >
                                        <Pencil size={12} />
                                    </button>
                                    <button
                                        type="button"
                                        className="chat-project-icon"
                                        onClick={() => void clearActiveChat()}
                                        disabled={!activeChatId || savingChatMeta}
                                        title="Clear project memory"
                                    >
                                        <RotateCcw size={12} />
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                    {aiMode === 'ai' && (
                        <span className="ai-mode-badge ai-powered">
                            <Sparkles size={12} /> {providerLabel}
                        </span>
                    )}
                    {aiMode === 'keyword' && (
                        <span className="ai-mode-badge keyword-mode">
                            <AlertTriangle size={12} /> Basic Mode
                        </span>
                    )}
                </div>
                <div className="chat-header-right">
                    <button
                        type="button"
                        className={`usage-toggle-btn ${usageOpen ? 'active' : ''}`}
                        onClick={toggleUsage}
                        title="AI Usage"
                    >
                        <BarChart3 size={16} />
                        <span>Usage</span>
                    </button>
                    <div className={`uefn-badge ${uefnConnected ? 'connected' : 'disconnected'}`}>
                        <span className="dot" />
                        {uefnConnected ? 'UEFN Connected' : 'UEFN Offline'}
                    </div>
                </div>
            </div>

            {aiMode === 'keyword' && messages.length === 0 && (
                <div className="ai-mode-banner">
                    <AlertTriangle size={16} />
                    <span>
                        Running in basic mode. Set up <strong>Groq</strong> (free, 30 sec) or <strong>Ollama</strong> (free, local) in <strong>Settings</strong> for real AI.
                    </span>
                </div>
            )}

            <div className="chat-shell">
                <aside className={`chat-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
                    <div className="chat-sidebar-header chat-sidebar-brand">
                        <div className="chat-sidebar-brandmark">
                            <Bot size={16} />
                        </div>
                        <button
                            type="button"
                            className="chat-sidebar-icon-btn"
                            onClick={() => {
                                const next = !sidebarCollapsed;
                                setSidebarCollapsed(next);
                                localStorage.setItem('_codex_sidebar_collapsed', String(next));
                            }}
                            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                        >
                            <PanelLeft size={15} />
                        </button>
                    </div>

                    <div className="chat-sidebar-actions">
                        <button type="button" className="chat-sidebar-action-btn primary" onClick={() => void createChat(true, '')} title="New chat">
                            <Pencil size={16} />
                            {!sidebarCollapsed && <span>New chat</span>}
                        </button>
                        <button
                            type="button"
                            className={`chat-sidebar-action-btn ${showChatSearch ? 'active' : ''}`}
                            onClick={() => setShowChatSearch(prev => !prev)}
                            title="Search chats"
                        >
                            <Search size={16} />
                            {!sidebarCollapsed && <span>Search chats</span>}
                        </button>
                    </div>

                    {showChatSearch && (
                        <div className="chat-sidebar-search">
                            <Search size={15} />
                            <input
                                ref={chatSearchInputRef}
                                type="text"
                                placeholder="Search chats"
                                value={chatSearchQuery}
                                onChange={(e) => setChatSearchQuery(e.target.value)}
                            />
                        </div>
                    )}

                    {/* Projects section */}
                    <div className="chat-sidebar-section">
                        <div className="chat-sidebar-section-title">Projects</div>
                        <button type="button" className="chat-sidebar-link-btn" onClick={() => void createProject()}>
                            <FolderPlus size={16} />
                            <span>New project</span>
                        </button>
                    </div>
                    <div className="chat-sidebar-projects">
                        {projects.map(proj => {
                            const isExpanded = expandedProjects.has(proj.id);
                            const projChats = projectChatsMap[proj.id] || [];
                            const projIcon = proj.icon || '📁';
                            const projColor = proj.color || '';
                            return (
                                <div key={proj.id} className="project-folder">
                                    <div
                                        className={`project-folder-header ${proj.id === activeProjectId ? 'active' : ''}`}
                                        onClick={() => void toggleProjectExpand(proj.id)}
                                        role="button"
                                        tabIndex={0}
                                        style={projColor ? { borderLeftColor: projColor } : undefined}
                                    >
                                        <ChevronDown size={12} className={`project-chevron ${isExpanded ? 'open' : ''}`} />
                                        <span
                                            className="project-icon-btn"
                                            onClick={(e) => { e.stopPropagation(); setIconPickerProjectId(iconPickerProjectId === proj.id ? '' : proj.id); setColorPickerProjectId(''); }}
                                            title="Change icon"
                                        >
                                            {projIcon}
                                        </span>
                                        {editingProjectId === proj.id ? (
                                            <input
                                                className="chat-sidebar-project-input"
                                                value={projectNameDraft}
                                                autoFocus
                                                onChange={(e) => setProjectNameDraft(e.target.value)}
                                                onBlur={() => renameProject(proj.id, projectNameDraft)}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter') { e.preventDefault(); renameProject(proj.id, projectNameDraft); }
                                                    if (e.key === 'Escape') setEditingProjectId('');
                                                    e.stopPropagation();
                                                }}
                                                onClick={(e) => e.stopPropagation()}
                                            />
                                        ) : (
                                            <span className="project-folder-name">{proj.name}</span>
                                        )}
                                        <span className="project-folder-count">{proj.chat_count || projChats.length}</span>
                                        <div className="project-folder-actions" onClick={(e) => e.stopPropagation()}>
                                            <button type="button" title="New chat" onClick={() => void newChatInProject(proj.id)}><Plus size={11} /></button>
                                            <button type="button" title="Color" onClick={() => { setColorPickerProjectId(colorPickerProjectId === proj.id ? '' : proj.id); setIconPickerProjectId(''); }}>
                                                <span className="color-dot" style={{ background: projColor || '#666' }} />
                                            </button>
                                            <button type="button" title="Rename" onClick={() => { setEditingProjectId(proj.id); setProjectNameDraft(proj.name); }}><Pencil size={11} /></button>
                                            <button type="button" title="Delete" className="delete" onClick={() => void deleteProject(proj.id)}><Trash2 size={11} /></button>
                                        </div>
                                    </div>

                                    {/* Icon picker popout */}
                                    {iconPickerProjectId === proj.id && (
                                        <div className="project-picker-popout icon-picker" onClick={(e) => e.stopPropagation()}>
                                            <div className="picker-grid">
                                                {PROJECT_ICONS.map(ic => (
                                                    <button
                                                        key={ic}
                                                        type="button"
                                                        className={`picker-item ${ic === projIcon ? 'active' : ''}`}
                                                        onClick={(e) => { e.stopPropagation(); void updateProjectIcon(proj.id, ic); }}
                                                    >
                                                        {ic}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Color picker popout */}
                                    {colorPickerProjectId === proj.id && (
                                        <div className="project-picker-popout color-picker" onClick={(e) => e.stopPropagation()}>
                                            <div className="picker-grid color-grid">
                                                {PROJECT_COLORS.map((c, i) => (
                                                    <button
                                                        key={i}
                                                        type="button"
                                                        className={`picker-color-item ${c === projColor ? 'active' : ''}`}
                                                        style={{ background: c || '#333' }}
                                                        onClick={(e) => { e.stopPropagation(); void updateProjectColor(proj.id, c); }}
                                                        title={c || 'No color'}
                                                    >
                                                        {c === projColor && <Check size={10} />}
                                                        {!c && !projColor && <X size={10} />}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Expanded: show chats inside this project */}
                                    {isExpanded && (
                                        <div className="project-folder-chats">
                                            {projChats.length === 0 ? (
                                                <div className="project-chat-empty">No chats yet</div>
                                            ) : (
                                                projChats.map(chat => (
                                                    <div
                                                        key={chat.id}
                                                        className={`project-chat-item ${chat.id === activeChatId ? 'active' : ''}`}
                                                        onClick={() => selectProjectChat(proj.id, chat.id)}
                                                        role="button"
                                                        tabIndex={0}
                                                    >
                                                        <MessageSquare size={12} />
                                                        {renamingChatId === chat.id ? (
                                                            <input
                                                                className="project-chat-rename-input"
                                                                value={renamingChatDraft}
                                                                autoFocus
                                                                onChange={(e) => setRenamingChatDraft(e.target.value)}
                                                                onBlur={() => void renameChat(chat.id, renamingChatDraft, proj.id)}
                                                                onKeyDown={(e) => {
                                                                    if (e.key === 'Enter') { e.preventDefault(); void renameChat(chat.id, renamingChatDraft, proj.id); }
                                                                    if (e.key === 'Escape') setRenamingChatId('');
                                                                    e.stopPropagation();
                                                                }}
                                                                onClick={(e) => e.stopPropagation()}
                                                            />
                                                        ) : (
                                                            <span className="project-chat-title">{chat.title || 'New Chat'}</span>
                                                        )}
                                                        <span className="project-chat-meta">{chat.message_count} msg</span>
                                                        <button
                                                            type="button"
                                                            className="project-chat-action"
                                                            onClick={(e) => { e.stopPropagation(); setRenamingChatId(chat.id); setRenamingChatDraft(chat.title || ''); }}
                                                            title="Rename"
                                                        >
                                                            <Pencil size={10} />
                                                        </button>
                                                        <button
                                                            type="button"
                                                            className="project-chat-action delete"
                                                            onClick={(e) => { e.stopPropagation(); void deleteChat(chat.id); setProjectChatsMap(prev => ({ ...prev, [proj.id]: (prev[proj.id] || []).filter(c => c.id !== chat.id) })); }}
                                                            title="Delete"
                                                        >
                                                            <Trash2 size={10} />
                                                        </button>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Standalone chats section */}
                    <div className="chat-sidebar-section">
                        <div className="chat-sidebar-section-title">Your chats</div>
                    </div>

                    <div className="chat-sidebar-list chat-sidebar-list-styled">
                        {loadingChats ? (
                            <div className="chat-sidebar-empty">Loading chats…</div>
                        ) : filteredChats.length === 0 ? (
                            <div className="chat-sidebar-empty">
                                {chatSearchQuery ? 'No chats match your search.' : 'No chats yet.'}
                            </div>
                        ) : (
                            filteredChats.map(chat => (
                                <div
                                    key={chat.id}
                                    role="button"
                                    tabIndex={0}
                                    className={`chat-thread ${chat.id === activeChatId ? 'active' : ''}`}
                                    onClick={() => void selectChat(chat.id)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter' || e.key === ' ') {
                                            e.preventDefault();
                                            void selectChat(chat.id);
                                        }
                                    }}
                                >
                                    <div className="chat-thread-top">
                                        <div className="chat-thread-title-wrap">
                                            <MessageSquare size={14} />
                                            {renamingChatId === chat.id ? (
                                                <input
                                                    className="project-chat-rename-input"
                                                    value={renamingChatDraft}
                                                    autoFocus
                                                    onChange={(e) => setRenamingChatDraft(e.target.value)}
                                                    onBlur={() => void renameChat(chat.id, renamingChatDraft)}
                                                    onKeyDown={(e) => {
                                                        if (e.key === 'Enter') { e.preventDefault(); void renameChat(chat.id, renamingChatDraft); }
                                                        if (e.key === 'Escape') setRenamingChatId('');
                                                        e.stopPropagation();
                                                    }}
                                                    onClick={(e) => e.stopPropagation()}
                                                />
                                            ) : (
                                                <span className="chat-thread-title">{chat.title}</span>
                                            )}
                                        </div>
                                        <div className="chat-thread-actions">
                                            <button
                                                type="button"
                                                className="chat-thread-action"
                                                onClick={(e) => { e.stopPropagation(); setRenamingChatId(chat.id); setRenamingChatDraft(chat.title || ''); }}
                                                title="Rename chat"
                                            >
                                                <Pencil size={11} />
                                            </button>
                                            <button
                                                type="button"
                                                className="chat-thread-action delete"
                                                onClick={(e) => { e.stopPropagation(); void deleteChat(chat.id); }}
                                                title="Delete chat"
                                            >
                                                <Trash2 size={11} />
                                            </button>
                                        </div>
                                    </div>
                                    <div className="chat-thread-preview">
                                        {chat.preview || 'No messages yet'}
                                    </div>
                                    <div className="chat-thread-meta">
                                        <span>{chat.message_count} msg</span>
                                        <span>{formatSidebarTime(chat.updated_at)}</span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </aside>

                <div className="chat-main">
                    <div className="chat-body">
                        <div className="chat-messages">
                            {loadingChat ? (
                                <div className="chat-empty">
                                    <Bot size={42} />
                                    <h3>Loading chat</h3>
                                    <p>Restoring stored conversation and memory for this project.</p>
                                </div>
                            ) : messages.length === 0 ? (
                                <div className="chat-empty">
                                    <Bot size={48} />
                                    <h3>UEFN AI Assistant</h3>
                                    <p>
                                        Ask me anything about your project. I can query your UEFN level,
                                        run tools, check actors, and help you build.
                                    </p>
                                    <div className="chat-suggestions">
                                        {SUGGESTIONS.map((suggestion, index) => (
                                            <button key={index} type="button" className="suggestion-chip" onClick={() => void sendMessage(suggestion)}>
                                                {suggestion}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                messages.map(message => (
                                    <div key={message.id} className={`message-row ${message.role}`}>
                                        <div className="message-avatar">
                                            {message.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
                                        </div>
                                        <div className="message-bubble">
                                            {message.attachments && message.attachments.length > 0 && (
                                                <div className="msg-attachments">
                                                    {message.attachments.map((attachment, index) => (
                                                        <button
                                                            key={index}
                                                            type="button"
                                                            className="msg-attach-chip clickable"
                                                            onClick={() => openAttachmentViewer(attachment, 'message')}
                                                        >
                                                            {attachment.type === 'image' && attachment.content ? (
                                                                <img src={attachment.content} alt="" className="attach-chip-thumb" />
                                                            ) : null}
                                                            {attachment.type === 'image' ? <ImageIcon size={12} /> : <FileText size={12} />}
                                                            {attachment.name}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                            <div className="msg-text">{renderContent(message.content)}</div>
                                            {message.toolResult && (
                                                <details className="msg-tool-result">
                                                    <summary className="tool-label">Tool: {message.toolResult.tool}</summary>
                                                    <pre>{formatToolOutput(message.toolResult.output).substring(0, 2000)}</pre>
                                                </details>
                                            )}
                                            <span className="msg-time">{formatClock(message.timestamp)}</span>
                                        </div>
                                    </div>
                                ))
                            )}

                            {sending && (
                                <div className="typing-indicator">
                                    <div className="message-avatar" style={{ background: 'linear-gradient(135deg, #6366f1, #818cf8)' }}>
                                        <Bot size={16} color="white" />
                                    </div>
                                    <div className="typing-dots">
                                        <span /><span /><span />
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {usageOpen && (
                            <div className="usage-side-panel">
                                <div className="usage-side-header">
                                    <h3><BarChart3 size={16} /> AI Usage</h3>
                                    <button type="button" className="usage-close" onClick={() => setUsageOpen(false)}>
                                        <X size={16} />
                                    </button>
                                </div>
                                <div className="usage-side-date">{usageDate || 'Today'}</div>

                                {usageData ? (
                                    Object.entries(usageData).length > 0 ? (
                                        Object.entries(usageData).map(([provider, info]) => {
                                            const isActive = provider === aiProvider;
                                            const hasLimit = info.limit_requests > 0 || info.limit_tokens > 0;
                                            return (
                                                <div key={provider} className={`usage-card ${isActive ? 'active' : ''}`}>
                                                    <div className="usage-card-header">
                                                        <span className="usage-card-name">
                                                            {isActive && <span className="usage-active-dot" />}
                                                            {info.label}
                                                        </span>
                                                        <span className="usage-card-count">{info.requests} req</span>
                                                    </div>
                                                    {hasLimit && (
                                                        <div className="usage-bar-container">
                                                            <div
                                                                className="usage-bar"
                                                                style={{
                                                                    width: `${Math.min(info.percent_used, 100)}%`,
                                                                    backgroundColor: getBarColor(info.percent_used),
                                                                }}
                                                            />
                                                        </div>
                                                    )}
                                                    <div className="usage-card-details">
                                                        {info.limit_requests > 0 && (
                                                            <span>{formatNumber(info.requests)} / {formatNumber(info.limit_requests)} requests</span>
                                                        )}
                                                        {info.limit_tokens > 0 && (
                                                            <span>{formatNumber(info.tokens_total)} / {formatNumber(info.limit_tokens)} tokens</span>
                                                        )}
                                                        {!hasLimit && info.period === 'unlimited' && (
                                                            <span className="usage-unlimited-label">Unlimited</span>
                                                        )}
                                                        {info.tokens_total > 0 && (
                                                            <span className="usage-tokens-detail">
                                                                {formatNumber(info.tokens_in)} in / {formatNumber(info.tokens_out)} out
                                                            </span>
                                                        )}
                                                    </div>
                                                    {hasLimit && info.percent_used > 0 && (
                                                        <div className="usage-pct-label">{info.percent_used}% used</div>
                                                    )}
                                                </div>
                                            );
                                        })
                                    ) : (
                                        <div className="usage-empty">No usage data yet — send a message first</div>
                                    )
                                ) : (
                                    <div className="usage-empty">Loading usage data...</div>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="chat-input-area">
                        {attachments.length > 0 && (
                            <div className="chat-attach-row">
                                {attachments.map((attachment, index) => (
                                    <div
                                        key={index}
                                        className="attach-chip clickable"
                                        onClick={() => openAttachmentViewer(attachment, 'composer')}
                                        role="button"
                                        tabIndex={0}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' || e.key === ' ') {
                                                e.preventDefault();
                                                openAttachmentViewer(attachment, 'composer');
                                            }
                                        }}
                                    >
                                        {attachment.type === 'image' && attachment.content ? (
                                            <img src={attachment.content} alt="" className="attach-chip-thumb" />
                                        ) : null}
                                        {attachment.type === 'image' ? <ImageIcon size={12} /> : <FileText size={12} />}
                                        {attachment.name}
                                        <span className="attach-chip-meta">
                                            {attachment.type === 'image' ? 'Image' : attachment.type === 'binary' ? 'Binary' : 'File'}
                                            {attachment.sourceUrl ? ' • Web' : ''}
                                            {attachment.analysisCaption ? ' • Vision' : ''}
                                            {attachment.analysisHandwriting ? ' • HTR' : ''}
                                            {attachment.analysisText ? ' • OCR' : ''}
                                        </span>
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                removeAttachment(index);
                                            }}
                                            aria-label="Remove"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                        <div className="chat-input-row">
                            <button
                                type="button"
                                className="chat-attach-btn"
                                onClick={() => fileInputRef.current?.click()}
                                title="Attach file"
                            >
                                <Plus size={18} />
                            </button>

                            <input
                                ref={fileInputRef}
                                type="file"
                                multiple
                                className="chat-file-input"
                                onChange={(e) => {
                                    Array.from(e.target.files || []).forEach(file => {
                                        void addFile(file);
                                    });
                                    e.target.value = '';
                                }}
                            />
                            <textarea
                                ref={textareaRef}
                                placeholder="Ask about your UEFN project..."
                                value={input}
                                onChange={(e) => handleInputChange(e.target.value)}
                                onKeyDown={handleKeyDown}
                                onPaste={handleComposerPaste}
                                rows={1}
                            />
                            <button
                                type="button"
                                className="chat-send-btn"
                                onClick={() => void sendMessage()}
                                disabled={sending || (!input.trim() && attachments.length === 0)}
                            >
                                <Send size={18} />
                            </button>
                        </div>
                        <div className="chat-input-meta-row" ref={modelMenuRef}>
                            <div className="input-model-switcher">
                                <button
                                    type="button"
                                    className="input-model-btn"
                                    onClick={() => setModelMenuOpen(!modelMenuOpen)}
                                    title={aiMode === 'ai' ? `Active provider: ${providerLabel}` : 'Switch AI provider'}
                                >
                                    <Sparkles size={12} />
                                    <span className="input-model-name">
                                        {aiMode === 'ai' ? providerLabel : 'Basic Mode'}
                                    </span>
                                    <ChevronDown size={10} />
                                </button>
                                {modelMenuOpen && (
                                    <div className="input-model-dropdown">
                                        <div className="model-dropdown-header">Switch Provider</div>
                                        <div className="model-dropdown-subtext">Pick the exact model version in Settings.</div>
                                        {switcherProviders.length === 0 && (
                                            <div className="model-dropdown-empty">
                                                No providers configured. Go to <strong>Settings</strong> to add API keys.
                                            </div>
                                        )}
                                        {switcherProviders.map(({ prov, label }) => (
                                            <button
                                                key={prov}
                                                type="button"
                                                className={`model-option ${prov === aiProvider ? 'active' : ''}`}
                                                onClick={() => void switchModel(prov)}
                                                disabled={switchingModel}
                                            >
                                                <span>{label}</span>
                                                {prov === aiProvider && <Check size={14} />}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                            <span className="input-meta-hint">
                                {uefnConnected ? 'UEFN connected — AI can read & modify your level' : 'UEFN offline'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default ChatPanel;
