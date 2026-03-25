# UEFN Codex Agent - Unified Integration Guide

## Overview

The UEFN Codex Agent is a comprehensive, modern desktop application that integrates:

- **UEFN-TOOLBELT**: 161 professional tools for UEFN development
- **Asset AI**: Intelligent asset catalog and management system
- **Codex Integration**: AI-powered planning and orchestration
- **Modern Electron UI**: Beautiful, responsive desktop interface

This document covers everything you need to know to use, develop, and contribute to the project.

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              UEFN Codex Agent (Electron App)            │
│  ┌────────────────────────────────────────────────────┐ │
│  │  React Frontend (TypeScript + Tailwind)            │ │
│  │  - Tool Dashboard (161+ tools)                     │ │
│  │  - Asset Browser                                   │ │
│  │  - Codex Planning Panel                           │ │
│  │  - Configuration UI                               │ │
│  └──────────────────┬─────────────────────────────────┘ │
│                     │ IPC / HTTP                         │
│  ┌──────────────────▼─────────────────────────────────┐ │
│  │  Electron Main Process (TypeScript)                │ │
│  │  - Window lifecycle management                     │ │
│  │  - IPC message routing                             │ │
│  │  - Python subprocess management                    │ │
│  └──────────────────┬─────────────────────────────────┘ │
└─────────────────────┼──────────────────────────────────┘
                      │ HTTP / WebSocket
                      ▼
┌─────────────────────────────────────────────────────────┐
│           Python FastAPI Backend Server                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Tool Registry & Discovery                         │ │
│  │  - Loads tool_manifest.json (161 tools)           │ │
│  │  - Dynamic tool execution                          │ │
│  │  - Execution history & logging                     │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  UEFN MCP Bridge                                   │ │
│  │  - Connects to UEFN MCP Server (127.0.0.1:8765)   │ │
│  │  - Forwards tool execution commands               │ │
│  │  - Returns structured results                      │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Asset AI Interface                                │ │
│  │  - Loads asset shortlist from catalog             │ │
│  │  - Provides trust scores & metadata               │ │
│  │  - Search & filtering                              │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
   UEFN Editor  Codex Bridge   Asset Catalog
  (MCP Server)  (Planning AI)   (JSON Files)
```

## Installation & Setup

### Requirements

- **Windows 10+** (or macOS/Linux)
- **Python 3.11+** - Download from [python.org](https://www.python.org/downloads/)
- **Node.js 20+** - Download from [nodejs.org](https://nodejs.org/)
- **UEFN** with Python enabled

### Quick Setup

#### Windows

```bash
# Run the setup script
setup.bat

# This will:
# 1. Check Python installation
# 2. Create Python virtual environment
# 3. Install Python dependencies
# 4. Check Node.js installation
# 5. Install Node.js packages
```

#### macOS / Linux

```bash
# Make script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

### Manual Setup

If the scripts don't work, follow these steps:

```bash
# 1. Create Python environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate.bat  # Windows

# 2. Install Python dependencies
pip install -r app/backend/requirements.txt

# 3. Install Node dependencies
cd app/electron
npm install
cd ../..
```

## Running the Application

### Starting the Servers

You only need one terminal window from the root `unreal-codex-agent` folder:

```bash
# 1. Activate Python environment
.venv\Scripts\activate.bat  # Windows
source .venv/bin/activate   # macOS/Linux

# 2. Start both Frontend and Backend
npm start

# The app is accessible at http://localhost:3000
# The browser will automatically open for you!
```

### Backend Only

```bash
# Activate Python environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate.bat  # Windows

# Run backend server
python app/backend/server.py

# Server runs on http://127.0.0.1:8000
```

## Using the Application

### Dashboard

The main dashboard shows system statistics and quick actions:
- **Tools Loaded**: Number of available UEFN-TOOLBELT tools
- **Categories**: Tool organization categories
- **Backend Status**: Connection status to API server

### Tool Dashboard

Browse and execute any of the 161 UEFN-TOOLBELT tools:

1. **Search or Filter**: Use the sidebar to search or filter by category
2. **Select Tool**: Click any tool card to view details
3. **Configure Parameters**: Enter parameters if required
4. **Execute**: Click "Execute Tool" to run
5. **View Results**: See structured output in the results panel

### Asset Browser

Browse assets from your Asset AI catalog:

1. **Search**: Use the search box to find assets
2. **Filter**: Filter by asset type
3. **Preview**: Click an asset to see full details
4. **View Properties**: See dimensions, trust scores, and metadata

### Codex Planning

Use AI-powered planning to generate island layouts:

1. **Describe**: Write what you want to build
2. **Set Goals**: Define primary objectives
3. **Add Constraints**: List any limitations
4. **Generate**: Click "Generate Plan" 
5. **Review**: See planned steps and required tools

### Settings

Configure application settings:
- View application information
- Check backend configuration
- Manage UEFN connection settings
- Save preferences

## API Reference

### RESTful Endpoints

All endpoints are HTTP-based on `http://127.0.0.1:8000`

#### Health & Info

```bash
# Server health check
GET /api/health

# Server info
GET /

# Application config
GET /api/config
```

#### Tools Management

```bash
# Get all tools
GET /api/tools

# Get tool categories
GET /api/tools/categories

# Get tools in category
GET /api/tools/category/{category}

# Search tools
GET /api/tools/search?query=<query>

# Get specific tool info
GET /api/tools/{tool_name}

# Execute tool
POST /api/tools/{tool_name}/execute
Content-Type: application/json

{
    "parameter_name": "value"
}

# Get execution history
GET /api/tools/history?limit=50
```

#### Assets

```bash
# Get asset shortlist
GET /api/assets/shortlist

# Filter by type
GET /api/assets/shortlist?asset_type=<type>

# Search assets
GET /api/assets/search?query=<query>
```

#### Codex Integration

```bash
# Create planning request
POST /api/codex/plan
Content-Type: application/json

{
    "description": "What to build",
    "goals": "Primary objectives",
    "constraints": "Limitations",
    "selectedAssets": []
}

# Get planning history
GET /api/codex/history
```

### WebSocket Support

Real-time tool execution:

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://127.0.0.1:8000/ws/tools');

// Send command
ws.send(JSON.stringify({
    action: 'execute',
    tool: 'tool_name',
    parameters: { key: 'value' }
}));

// Receive result
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Result:', data.result);
};
```

## Integration Points

### With Existing Codex Agent

The backend connects to your existing:

1. **Asset AI** (`apps/asset_ai/`) - Loads shortlists
2. **Capture Service** (`apps/capture_service/`) - For multi-angle capture
3. **Validation** (`apps/validation/`) - For pre-execution checks
4. **Orchestrator** (`apps/orchestrator/`) - For planning loop

Configuration is in `app/backend/server.py`:

```python
ASSET_AI_PATH = APPS_DIR / "asset_ai"
CODEX_BRIDGE_PATH = APPS_DIR / "codex_bridge"
CAPTURE_SERVICE_PATH = APPS_DIR / "capture_service"
VALIDATION_PATH = APPS_DIR / "validation"
```

### With UEFN-TOOLBELT

The app automatically discovers tools via:

1. **Tool Manifest**: `tool_manifest.json` (161 tools indexed)
2. **Tool Registry**: Organized by category
3. **MCP Bridge**: Connects to UEFN on `127.0.0.1:8765`

### Tool Execution Flow

```
User Click → Tool Selected → Parameters Set → 
Execute Button → API Call → UEFN MCP Bridge →
UEFN Editor → Executes Python Code → 
Returns Dict Result → Displayed in UI
```

## Development Guide

### Project Structure

```
unreal-codex-agent/
├── app/
│   ├── backend/              # Python FastAPI server
│   │   ├── server.py         # Main application
│   │   └── requirements.txt  # Python dependencies
│   ├── electron/             # Electron app entry
│   │   ├── package.json      # Electron config
│   │   ├── src/
│   │   │   ├── main.ts       # Electron main process
│   │   │   └── preload.ts    # Security preload
│   │   └── build/            # Compiled output
│   └── frontend/             # React frontend
│       ├── src/
│       │   ├── App.tsx       # Main component
│       │   ├── components/   # React components
│       │   ├── styles/       # Component styles
│       │   └── index.tsx     # Entry point
│       ├── public/           # Static assets
│       └── tsconfig.json
└── vendor/uefn-toolbelt/     # UEFN-TOOLBELT (vendored)
```

### Adding Features

#### Add a Backend Endpoint

1. Edit `app/backend/server.py`
2. Define a new endpoint:

```python
@app.get("/api/my-feature")
async def my_feature():
    return {"status": "ok", "data": []}
```

3. Test with curl or Postman

#### Add a Frontend Component

1. Create component in `app/frontend/src/components/MyComponent.tsx`
2. Add to `App.tsx` routes
3. Style with CSS in `app/frontend/src/styles/`

#### Add a Tool

Tools are auto-discovered from `vendor/uefn-toolbelt/`:

1. Register tool with `@register_tool` decorator
2. Run backend - tool appears automatically
3. Frontend automatically lists it

### Building & Distribution

```bash
# Production build
cd app/electron
npm run build

# Creates:
# - dist/uefn-codex-app-1.0.0.exe (Windows)
# - dist/uefn-codex-app-1.0.0.dmg (macOS)
# - dist/uefn-codex-agent-1.0.0.AppImage (Linux)
```

## Troubleshooting

### Backend not starting

```bash
# Check Python installation
python --version

# Check if port is in use
# Try:
python app/backend/server.py --port 8001
```

### UEFN not connecting

```bash
# Start UEFN MCP Server in UEFN:
import UEFN_Toolbelt as tb; tb.run("mcp_start")

# Verify connection
curl http://127.0.0.1:8765/api/health
```

### Frontend shows "Cannot connect to backend"

```bash
# Ensure backend is running
curl http://127.0.0.1:8000/

# Check if port 8000 is in use
# Restart both services
```

### Tool execution fails

1. Check UEFN is running
2. Check UEFN Python is enabled
3. View execution history in Settings for full error logs

## Performance Tips

1. **For large asset lists**: Use filters/search instead of loading all
2. **Tool execution**: Some tools are slow on first run - be patient
3. **Memory**: Close other applications if app is sluggish
4. **Network**: Direct connections (not VPN) work best with UEFN

## Security Considerations

- **IPC**: Uses Electron context isolation for security
- **API**: FastAPI runs locally (127.0.0.1) by default
- **WebSocket**: Secure via localhost
- **UEFN Connection**: MCP bridge validates commands

## Contributing

To contribute improvements:

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes
4. Test thoroughly
5. Submit pull request

Contributions welcome for:
- New UI components
- Additional tools
- Performance improvements
- Documentation
- Bug fixes

## License

This project integrates:
- **UEFN-TOOLBELT** (AGPL-3.0)
- **Existing Codex Agent** (Your license)
- **Custom integration code** (MIT)

Respect all original licenses when distributing or modifying.

## Support

For help:

1. Check the troubleshooting section
2. Review the [INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md)
3. Check existing GitHub issues
4. Create a new issue with detailed information

## Changelog

### v1.0.0 (Initial Release)

- ✓ Complete UEFN-TOOLBELT integration
- ✓ Modern Electron UI
- ✓ Tool discovery and execution
- ✓ Asset browser
- ✓ Codex planning panel
- ✓ Settings management
- ✓ Real-time status monitoring
- ✓ WebSocket support

---

**Happy building with UEFN Codex Agent!** 🚀
