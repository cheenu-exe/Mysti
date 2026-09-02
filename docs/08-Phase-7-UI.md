# Phase 7: User Interface

## Phase Overview

Phase 7 gives MYSTI a face — a web-based dashboard that provides a visual interface for all the capabilities built in previous phases. While the CLI is functional, a graphical interface makes MYSTI more accessible, more pleasant to use, and easier to monitor.

The dashboard brings together:
- **Chat interface** — Real-time conversation with MYSTI
- **Memory browser** — Browse, search, and manage your encrypted memories
- **Research feed** — View daily briefings and research findings
- **Security panel** — Manage permissions, view audit logs, control mode
- **Project tracker** — Visualize project progress and tasks
- **Settings** — Configure MYSTI's behavior and preferences

The UI is built with Next.js and React, using Tailwind CSS for styling and shadcn/ui for components. The design follows a dark theme aesthetic that matches your personal style.

---

## Goals and Success Criteria

### Primary Goals

1. **Chat interface** — Real-time conversation with markdown rendering and code highlighting.
2. **Memory browser** — Browse, search, and manage encrypted memories with category filters.
3. **Research feed** — View daily briefings, research items, and bookmark important findings.
4. **Security panel** — Manage permissions, view audit logs, toggle mode, emergency stop.
5. **Project dashboard** — Visualize project progress, tasks, and milestones.
6. **Settings panel** — Configure API keys, model selection, research sources, and preferences.
7. **Responsive design** — Works on desktop and tablet devices.

### Success Criteria

You know Phase 7 is complete when:

- You can have a real-time conversation with MYSTI through a web browser
- You can browse your memories with search and category filters
- You can view daily briefings and research findings in a clean feed
- You can manage permissions and view audit logs in the security panel
- You can track project progress with visual indicators
- You can configure MYSTI's settings through the UI
- The interface is responsive and works on different screen sizes

---

## Architecture

### What Phase 7 Adds

Phase 7 adds the frontend layer:

```
Existing Components:
├── FastAPI Backend (all phases)
├── Memory System
├── Research System
├── Security Layer
├── Tool System
├── Knowledge Graph
└── Self-Improvement Loop

Phase 7 Adds:
├── Next.js Frontend
│   ├── Pages (routes)
│   ├── Components (reusable UI elements)
│   ├── State Management (Zustand)
│   └── API Client (backend communication)
├── Real-time Communication (WebSocket)
├── Dark Theme Styling
└── Responsive Layout
```

### Communication Flow

The frontend communicates with the backend through:

```
Browser
    ↓
Next.js Frontend
    ↓
HTTP Requests (REST API)
    ↓
FastAPI Backend
    ↓
MYSTI Core

For real-time features:
Browser
    ↓
WebSocket Connection
    ↓
FastAPI WebSocket Endpoint
    ↓
MYSTI Core
    ↓
Streaming Response
    ↓
Browser
```

### Page Structure

The dashboard is organized into main pages:

```
/ (Dashboard)
├── /chat — Conversation interface
├── /memory — Memory browser
├── /research — Research feed
├── /security — Security panel
├── /projects — Project tracker
├── /models — Model registry and benchmarks
└── /settings — Configuration
```

---

## Data Models (Frontend State)

### Chat State

Manages the conversation interface.

**State:**

- `messages` — List of messages in the current conversation
- `sessionId` — Current conversation session ID
- `isTyping` — Whether MYSTI is generating a response
- `inputValue` — Current text in the input field

### Memory State

Manages the memory browser.

**State:**

- `memories` — List of memories currently displayed
- `selectedMemory` — Currently selected memory for detail view
- `searchQuery` — Current search query
- `selectedCategory` — Current category filter
- `isLoading` — Whether memories are being loaded

### Research State

Manages the research feed.

**State:**

- `briefings` — List of daily briefings
- `currentBriefing` — Currently viewed briefing
- `researchItems` — List of research items
- `bookmarkedItems` — Bookmarked research items
- `isLoading` — Whether research is being loaded

### Security State

Manages the security panel.

**State:**

- `currentMode` — Active or Passive mode
- `permissions` — List of active permissions
- `auditLog` — Recent audit log entries
- `sandboxStatus` — Status of active sandboxes
- `isLoading` — Whether security data is being loaded

### Project State

Manages the project tracker.

**State:**

- `projects` — List of projects
- `selectedProject` — Currently selected project
- `tasks` — Tasks for the selected project
- `milestones` — Milestones for the selected project
- `isLoading` — Whether project data is being loaded

---

## API Design (Frontend to Backend)

### Chat API

**Send message**

- Method: POST
- Path: /api/chat/message
- Request body: session_id, message
- Response: streaming response (SSE or WebSocket)
- Behavior: Sends the message to MYSTI and streams the response back.

**Get conversation history**

- Method: GET
- Path: /api/chat/history/{session_id}
- Query parameters: limit (default 50), offset
- Response: list of messages

**Start new conversation**

- Method: POST
- Path: /api/chat/new
- Response: session_id

### Memory API

**Search memories**

- Method: POST
- Path: /api/memory/search
- Request body: query, category, limit
- Response: list of memories with relevance scores

**Get memory details**

- Method: GET
- Path: /api/memory/{memory_id}
- Response: full memory details

**Create memory**

- Method: POST
- Path: /api/memory
- Request body: category, content, metadata
- Response: created memory details

**Delete memory**

- Method: DELETE
- Path: /api/memory/{memory_id}
- Response: confirmation

### Research API

**Get daily briefing**

- Method: GET
- Path: /api/research/briefing/today
- Response: briefing content

**List research items**

- Method: GET
- Path: /api/research/items
- Query parameters: source, category, min_score, limit
- Response: list of research items

**Bookmark research item**

- Method: POST
- Path: /api/research/items/{item_id}/bookmark
- Response: confirmation

### Security API

**Get security status**

- Method: GET
- Path: /api/security/status
- Response: current mode, permissions count, recent audit entries

**Switch mode**

- Method: POST
- Path: /api/security/mode
- Request body: mode (passive/active)
- Response: confirmation

**List permissions**

- Method: GET
- Path: /api/security/permissions
- Response: list of permissions

**Revoke permission**

- Method: DELETE
- Path: /api/security/permissions/{permission_id}
- Response: confirmation

**Get audit log**

- Method: GET
- Path: /api/security/audit
- Query parameters: limit, offset, action, status
- Response: list of audit log entries

**Emergency stop**

- Method: POST
- Path: /api/security/emergency-stop
- Response: confirmation

### Project API

**List projects**

- Method: GET
- Path: /api/projects
- Response: list of projects

**Get project details**

- Method: GET
- Path: /api/projects/{project_id}
- Response: full project details with tasks

**Update project**

- Method: PUT
- Path: /api/projects/{project_id}
- Request body: fields to update
- Response: updated project details

**Update task status**

- Method: PUT
- Path: /api/projects/{project_id}/tasks/{task_id}
- Request body: status
- Response: updated task details

---

## Implementation Details

### Step 1: Next.js Project Setup

**Project initialization**

Create a Next.js project with:
- TypeScript for type safety
- Tailwind CSS for styling
- shadcn/ui for pre-built components
- Zustand for state management

**Directory structure**

```
ui/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── chat/
│   │   └── page.tsx
│   ├── memory/
│   │   └── page.tsx
│   ├── research/
│   │   └── page.tsx
│   ├── security/
│   │   └── page.tsx
│   ├── projects/
│   │   └── page.tsx
│   ├── models/
│   │   └── page.tsx
│   └── settings/
│       └── page.tsx
├── components/
│   ├── ui/ (shadcn components)
│   ├── chat/
│   ├── memory/
│   ├── research/
│   ├── security/
│   └── layout/
├── lib/
│   ├── api.ts (API client)
│   ├── websocket.ts (WebSocket client)
│   └── utils.ts
├── stores/ (Zustand stores)
│   ├── chatStore.ts
│   ├── memoryStore.ts
│   ├── researchStore.ts
│   ├── securityStore.ts
│   └── projectStore.ts
└── styles/
    └── globals.css
```

### Step 2: Layout and Navigation

**Main layout**

The dashboard layout includes:
- Sidebar navigation (collapsible on mobile)
- Main content area
- Header with mode indicator and emergency stop button

**Navigation items:**

- Dashboard (home)
- Chat
- Memory
- Research
- Security
- Projects
- Models
- Settings

**Dark theme**

Apply a dark theme throughout:
- Background: Near-black (#0a0a0a)
- Surface: Dark gray (#1a1a1a)
- Border: Subtle gray (#2a2a2a)
- Text: Light gray (#e0e0e0)
- Primary: Cyan (#00d4ff) or your preferred accent
- Error: Red (#ff4444)
- Success: Green (#44ff44)

### Step 3: Chat Interface

**Message display**

Display messages in a conversation thread:
- User messages on the right (colored background)
- MYSTI messages on the left (neutral background)
- Markdown rendering for formatted text
- Code syntax highlighting for code blocks
- Timestamps for each message

**Input area**

Text input at the bottom:
- Multi-line text area (expandable)
- Send button
- Typing indicator when MYSTI is responding
- Keyboard shortcut: Enter to send, Shift+Enter for newline

**Real-time streaming**

Use Server-Sent Events (SSE) or WebSocket for streaming responses:
- Display tokens as they arrive
- Show a typing indicator during generation
- Handle connection errors gracefully

**Context panel**

Optional side panel showing:
- Relevant memories loaded for this conversation
- Related research items
- Active project context
- Entity information from knowledge graph

### Step 4: Memory Browser

**Memory list**

Display memories in a list or grid:
- Category icon and name
- Content preview (first 100 characters)
- Created/updated timestamps
- Relevance score (for search results)
- Click to view details

**Search bar**

Search functionality:
- Text input with search button
- Category filter dropdown
- Date range filter
- Sort options (relevance, date, category)

**Memory detail view**

When a memory is selected:
- Full content display
- Category and metadata
- Created/updated timestamps
- Related memories (from knowledge graph)
- Edit and delete buttons

**Create memory form**

Form to add new memories:
- Category selector
- Content text area
- Metadata fields (optional)
- Save button

### Step 5: Research Feed

**Daily briefing view**

Display today's briefing:
- Summary of items found
- Top items with relevance scores
- One-line summaries for each item
- Links to full content
- Bookmark buttons

**Research items list**

Browse all research items:
- Source icon and name
- Title and summary
- Relevance score
- Published date
- Bookmark status
- Filter by source, category, score

**Research item detail**

When an item is selected:
- Full content or summary
- Source information
- Relevance explanation
- Related items (from knowledge graph)
- Bookmark and note-taking options

**Briefing history**

View past briefings:
- Date selector
- Briefing content
- Item counts
- Trends over time

### Step 6: Security Panel

**Mode control**

Display and control the current mode:
- Large mode indicator (Passive/Active)
- Activate/Deactivate button
- Session timeout display
- Active permissions count

**Permission manager**

List and manage permissions:
- Table of active permissions
- Resource, action, scope, expiry
- Revoke button for each permission
- Grant new permission (for testing)

**Audit log viewer**

Browse the audit log:
- Filterable table of log entries
- Timestamp, action, resource, status
- Expandable details for each entry
- Export to CSV option

**Sandbox status**

Display sandbox information:
- Active sandbox count
- Resource usage (CPU, memory)
- Recent commands executed
- Destroy sandbox button

**Emergency stop**

Prominent emergency stop button:
- Red, always visible
- One-click to stop everything
- Confirmation dialog
- Status change notification

### Step 7: Project Dashboard

**Project list**

Display all projects:
- Project name and status
- Progress bar
- Priority indicator
- Deadline (if set)
- Quick status update

**Project detail**

When a project is selected:
- Full description
- Task list with checkboxes
- Milestone timeline
- Related technologies
- Related research
- Progress chart

**Task management**

Manage tasks within projects:
- Add new task
- Update task status (todo, in_progress, done)
- Set task priority
- Set due date
- Drag-and-drop reordering (optional)

### Step 8: Settings Panel

**API configuration**

Manage API keys and endpoints:
- OpenAI API key
- Anthropic API key
- Local model endpoint
- Connection test buttons

**Model selection**

Choose which models to use:
- Chat model selector
- Embedding model selector
- Model status indicators
- Performance comparison links

**Research sources**

Manage research sources:
- List of configured sources
- Add/remove sources
- Configure fetch intervals
- Enable/disable sources

**Notification preferences**

Configure notifications:
- Daily briefing delivery method
- Security alert preferences
- Desktop notification settings

**Data management**

Manage your data:
- Export all data
- Import data
- Clear conversation history
- Clear research items
- Backup and restore

---

## Dependencies

### New Dependencies for Phase 7

- **Next.js** — React framework
- **React** — UI library
- **TypeScript** — Type safety
- **Tailwind CSS** — Utility-first CSS
- **shadcn/ui** — Pre-built components
- **Zustand** — State management
- **Lucide React** — Icons

### Backend Changes

The FastAPI backend needs:
- Static file serving for the Next.js build
- WebSocket endpoint for real-time chat
- CORS configuration for development
- API documentation (Swagger UI)

---

## Testing

### Unit Tests

**Component tests**
- Test individual React components render correctly
- Test component interactions
- Test state management with Zustand
- Test API client functions

**Page tests**
- Test each page loads and displays correctly
- Test navigation between pages
- Test responsive behavior

### Integration Tests

**Chat flow**
- Test sending a message and receiving a response
- Test streaming response display
- Test conversation history loading

**Memory flow**
- Test searching memories
- Test viewing memory details
- Test creating and deleting memories

**Security flow**
- Test mode switching
- Test permission management
- Test audit log viewing
- Test emergency stop

### Visual Testing

**Responsive design**
- Test on desktop (1920x1080)
- Test on tablet (768x1024)
- Test on mobile (375x667)

**Dark theme**
- Verify all components respect the dark theme
- Check contrast ratios for accessibility
- Test with system dark/light mode preference

### Manual Testing

After Phase 7 is complete:
- Open the dashboard in a browser
- Have a conversation through the chat interface
- Browse your memories
- View the daily briefing
- Check the security panel
- Update a project task
- Change a setting
- Test emergency stop

---

## Edge Cases

### WebSocket Disconnection

If the WebSocket connection drops:
- Show a reconnection indicator
- Automatically attempt to reconnect
- Buffer messages during disconnection
- Display a warning if reconnection fails

### Slow Loading

If the backend is slow:
- Show loading spinners
- Provide skeleton UI placeholders
- Display error messages after timeout
- Allow manual retry

### Large Data Sets

If there are many memories or research items:
- Implement pagination
- Use virtual scrolling for long lists
- Load data progressively
- Cache frequently accessed data

### Browser Compatibility

Ensure compatibility across browsers:
- Chrome (primary)
- Firefox
- Edge
- Safari (limited support)

---

## Deliverables

When Phase 7 is complete, you will have:

1. **Web dashboard** — A complete web interface for MYSTI.

2. **Chat interface** — Real-time conversation with streaming responses.

3. **Memory browser** — Browse, search, and manage encrypted memories.

4. **Research feed** — View daily briefings and research findings.

5. **Security panel** — Manage permissions, view audit logs, control mode.

6. **Project dashboard** — Visualize project progress and tasks.

7. **Settings panel** — Configure MYSTI's behavior and preferences.

8. **Dark theme** — Consistent dark aesthetic throughout.

9. **Responsive design** — Works on desktop and tablet.

---

## What Comes Next

After Phase 7, you will move to **Phase 8: Advanced Features**, which adds:
- Voice interface (speech-to-text + text-to-speech with your cloned voice via Coqui TTS)
- Multi-model routing for cost optimization
- Backup and recovery
- Mobile PWA support

Phase 7's UI will serve as the foundation for these advanced features, with the chat interface supporting voice input and the settings panel managing backup configurations.

---

*Phase 7 makes MYSTI accessible and pleasant to use through a polished web interface.*
