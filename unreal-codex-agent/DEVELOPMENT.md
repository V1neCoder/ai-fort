# UEFN Codex Agent - Development Guide

## Overview

This guide covers everything needed to develop, test, and extend the UEFN Codex Agent unified application.

## Architecture

The application is split into 3 main layers:

### 1. Frontend Layer (React + Electron)

- **Location**: `app/frontend/src/`
- **Framework**: React 18 with TypeScript
- **Styling**: Custom CSS with dark theme
- **Components**:
  - `App.tsx` - Main routing and layout
  - `ToolDashboard.tsx` - Tool discovery and execution
  - `AssetBrowser.tsx` - Asset exploration
  - `CodexPanel.tsx` - AI planning interface
  - `SettingsPanel.tsx` - Configuration
  - `StatusBar.tsx` - Real-time status

### 2. Electron Layer (Main Process)

- **Location**: `app/electron/src/`
- **Process**: TypeScript compiled to JavaScript
- **Responsibilities**:
  - Window lifecycle management
  - IPC message routing
  - Python subprocess management
  - Menu and native features

### 3. Backend Layer (Python FastAPI)

- **Location**: `app/backend/server.py`
- **Framework**: FastAPI + Uvicorn
- **Features**:
  - RESTful API for all operations
  - Tool registry and discovery
  - UEFN MCP bridge
  - WebSocket support
  - Asset AI integration

## Development Workflow

### Starting Development

```bash
# Terminal 1: Backend
source .venv/bin/activate  # or .venv\Scripts\activate.bat
python app/backend/server.py

# Terminal 2: Frontend (in app/electron)
npm run react-start

# Terminal 3: Electron
npm run electron-dev
```

### Making Changes

#### Backend Changes

1. Edit `app/backend/server.py`
2. Backend hot-reloads automatically
3. Changes available at `http://127.0.0.1:8000`
4. Test with `curl` or API client

#### Frontend Changes

1. Edit components in `app/frontend/src/`
2. React hot-reloads automatically
3. See changes immediately in dev server

#### Electron Changes

1. Edit files in `app/electron/src/`
2. Rebuild main process: `npm run build-main`
3. Restart Electron to see changes

### Testing

#### Backend Tests

```bash
# Test API endpoint
curl http://127.0.0.1:8000/api/tools

# Test tool execution
curl -X POST http://127.0.0.1:8000/api/tools/tool_name/execute \
  -H "Content-Type: application/json" \
  -d '{"parameter": "value"}'

# Test WebSocket
wscat -c ws://127.0.0.1:8000/ws/tools
```

#### Frontend Tests

```bash
# In app/frontend
npm test

# Test specific component
npm test -- ToolDashboard

# With coverage
npm test -- --coverage
```

#### Integration Tests

```bash
# Test full flow: Frontend → Backend → UEFN → Result
# Manually test in the app or use:
npm run integration-test
```

## Key Concepts

### Tool Registry

The `ToolRegistry` class in backend manages all available tools:

```python
# Load tools
registry = ToolRegistry()

# Get tools
tools = registry.get_all_tools()

# Execute tool
result = await registry.execute_tool("tool_name", {"param": "value"})

# Search tools
results = registry.search_tools("keyword")
```

### UEFN Bridge

The `UEFNBridge` class handles connection to UEFN:

```python
# Check connection
connected = await uefn_bridge.check_connection()

# Execute through MCP
result = await uefn_bridge.run_tool("tool_name", parameters)

# Simulated execution (when UEFN not available)
result = uefn_bridge._simulate_tool_execution("tool", params)
```

### Component Data Flow

```
User Action → Component State → API Call → 
Backend Processing → Tool Execution → 
Result Processing → UI Update
```

Example:

```typescript
// User clicks execute
const executeTool = async (toolName: string) => {
    setExecuting(true);
    
    // API call
    const response = await axios.post(
        `${backendUrl}/api/tools/${toolName}/execute`,
        parameters
    );
    
    // Update UI
    setResults(response.data);
    setExecuting(false);
};
```

## Adding Features

### Adding a Backend Endpoint

1. **Define the endpoint** in `app/backend/server.py`:

```python
@app.get("/api/my-endpoint")
async def my_endpoint(param: str = None):
    """Description of what this does"""
    try:
        # Your logic here
        return {
            "status": "ok",
            "data": result,
            "message": "Success"
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error", "message": str(e)}
```

2. **Test locally**:

```bash
curl http://127.0.0.1:8000/api/my-endpoint?param=value
```

3. **Frontend component** calls it:

```typescript
const response = await axios.get(`${backendUrl}/api/my-endpoint`);
```

### Adding a React Component

1. **Create component**:

```typescript
// app/frontend/src/components/MyComponent.tsx
interface MyComponentProps {
    backendUrl: string;
}

function MyComponent({ backendUrl }: MyComponentProps) {
    const [data, setData] = useState([]);
    
    useEffect(() => {
        loadData();
    }, [backendUrl]);
    
    async function loadData() {
        const response = await axios.get(`${backendUrl}/api/my-endpoint`);
        setData(response.data);
    }
    
    return (
        <div className="my-component">
            {/* JSX here */}
        </div>
    );
}

export default MyComponent;
```

2. **Add to routing**:

```typescript
// app/frontend/src/App.tsx
<Route path="/my-page" element={<MyComponent backendUrl={state.backendUrl} />} />
```

3. **Add navigation link**:

```typescript
<Link to="/my-page" className="nav-link">
    <Icon size={18} />
    My Page
</Link>
```

### Adding Styles

1. **Create CSS file**: `app/frontend/src/styles/MyComponent.css`
2. **Import in component**: `import '../styles/MyComponent.css';`
3. **Use dark theme variables**:

```css
.my-component {
    background-color: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
}

.my-component:hover {
    background-color: rgba(58, 58, 255, 0.1);
}
```

## Debugging

### Backend Debugging

```python
# Add logging
import logging
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.error("Error message")

# Check in terminal where backend is running
```

### Frontend Debugging

```typescript
// Console logging
console.log('Debug:', variable);
console.error('Error:', error);

// React DevTools
// Install React DevTools extension in Chrome
// Check Components tab in browser DevTools
```

### Network Debugging

```javascript
// Monitor API calls
// Open browser DevTools → Network tab
// Make API call, see request/response

// Or use from backend logs
```

## Performance Optimization

### Frontend

1. **Memoization**:

```typescript
const MyComponent = React.memo(({ data }) => {
    return <div>{data}</div>;
});
```

2. **Lazy loading**:

```typescript
const MyComponent = React.lazy(() => import('./MyComponent'));

<Suspense fallback={<Loading />}>
    <MyComponent />
</Suspense>
```

3. **Code splitting**: Pages load on-demand via React Router

### Backend

1. **Caching**:

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_asset_shortlist():
    # Only computed once per day
    pass
```

2. **Async operations**:

```python
async def execute_tool(...):
    # Non-blocking execution
    pass
```

### Tool Execution

1. **Background tasks**:

```python
@app.post("/api/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(long_running_task, tool_name)
    return {"status": "queued"}
```

## Troubleshooting Development

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Use different port
python app/backend/server.py --port 8001
```

### Hot Reload Not Working

```bash
# Clear React cache
rm -rf app/frontend/.eslintcache

# Restart development servers
# Ctrl+C on all terminals
# Run dev commands again
```

### UEFN Connection Issues

```python
# Check manually
import asyncio
from app.backend.server import uefn_bridge

async def test():
    connected = await uefn_bridge.check_connection()
    print(f"Connected: {connected}")

asyncio.run(test())
```

## Database/Storage

Currently using:
- **JSON files** for tool history and configuration
- **Local storage** in browser for user preferences
- **In-memory** for current session data

Future improvements:
- SQLite for persistent history
- Better caching strategy
- Offline support

## Security

### Frontend Security

- Context isolation in Electron
- No eval() or dangerous APIs
- Validated inputs
- CORS enabled only for localhost

### Backend Security

- Input validation on all endpoints
- No eval() or dynamic code execution
- File operations confined to project directory
- Rate limiting ready (use middleware)

### UEFN Bridge Security

- Only connects to localhost UEFN MCP
- Commands validated before execution
- No untrusted code execution

## Building for Distribution

```bash
# Prepare build
cd app/electron
npm run build

# Creates:
# Windows: dist/*.exe
# macOS: dist/*.dmg
# Linux: dist/*.AppImage
```

## Resources

- [React Documentation](https://react.dev)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Electron Documentation](https://www.electronjs.org/docs)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

## Contributing

When contributing:

1. Follow existing code style
2. Test thoroughly
3. Update documentation
4. Create feature branch
5. Submit PR with description

---

Happy developing! 🛠️
