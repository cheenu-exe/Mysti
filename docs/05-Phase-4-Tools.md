# Phase 4: Tool Integration

## Phase Overview

Phase 4 gives MYSTI hands — the ability to actually interact with your computer. Before Phase 4, MYSTI could only think and research. After Phase 4, MYSTI can read and write files, execute terminal commands, browse the web, manage git repositories, and make network requests.

Every tool operation goes through the Policy Engine from Phase 3. No action is executed without permission. Every action is audited. The AI cannot self-grant permissions — it must request them from you, and you decide whether to allow each action.

The tools are organized through a **Tool Gateway** — a centralized layer that handles permission checking, execution, logging, and result formatting. This ensures that all tools follow the same security patterns and that adding new tools doesn't require duplicating security logic.

---

## Goals and Success Criteria

### Primary Goals

1. **Filesystem tool** — Read, write, search, and manage files within allowed directories.
2. **Terminal tool** — Execute commands in a sandboxed Docker container.
3. **Browser tool** — Navigate web pages, extract content, take screenshots.
4. **Git tool** — Repository operations (status, diff, commit, push with permission).
5. **Network tool** — HTTP requests with rate limiting and URL validation.
6. **Tool gateway** — Centralized orchestration, permission checking, and logging.
7. **Tool composition** — Chain multiple tools together for complex tasks.

### Success Criteria

You know Phase 4 is complete when:

- MYSTI can read a file you point it to (with your permission)
- MYSTI can create or modify files in designated directories
- MYSTI can execute terminal commands in an isolated sandbox
- MYSTI can browse a web page and extract its content
- MYSTI can check git status and create commits (with your approval for push)
- MYSTI can make HTTP requests to APIs you authorize
- Every tool action is logged and traceable
- You can compose multiple tools into a single workflow

---

## Architecture

### What Phase 4 Adds

Phase 4 adds the tool layer on top of the security infrastructure:

```
Phase 3 Components:
├── Policy Engine
├── Permission Manager
├── Mode Controller
├── Audit Logger
├── Sandbox Manager
└── Prompt Injection Defense

Phase 4 Adds:
├── Tool Gateway (orchestration layer)
├── Filesystem Tool
├── Terminal Tool
├── Browser Tool
├── Git Tool
├── Network Tool
└── Tool Composition Engine
```

### Tool Execution Flow

Every tool action follows this flow:

```
AI wants to perform an action
    ↓
AI calls Tool Gateway
    ↓
Tool Gateway identifies the tool and action
    ↓
Tool Gateway checks permission via Policy Engine
    ↓
If DENIED: return error to AI, log denial
    ↓
If APPROVED: route to appropriate tool
    ↓
Tool executes action (in sandbox if terminal)
    ↓
Tool returns result to Tool Gateway
    ↓
Tool Gateway logs result to Audit Logger
    ↓
Tool Gateway returns result to AI
```

### Tool Categories

Tools are organized by the type of system resource they access:

| Tool | Resource | Trust Level | Default Permission |
|------|----------|-------------|-------------------|
| Filesystem | Files and directories | T3 | Read: session, Write: single-use |
| Terminal | Shell commands | T3 | Single-use (per command) |
| Browser | Web content | T0-T3 | Navigate: session, Interact: single-use |
| Git | Version control | T3 | Read: session, Write: single-use, Push: single-use |
| Network | HTTP requests | T0-T1 | GET: session, POST: single-use |

---

## Data Models

### Tool Definition Record

Defines a registered tool.

**Fields:**

- `name` — Tool identifier (filesystem, terminal, browser, git, network).
- `description` — What the tool does.
- `actions` — List of supported actions with descriptions.
- `required_permissions` — Which permissions each action requires.
- `trust_level` — Minimum trust level for this tool.
- `enabled` — Whether the tool is currently available.
- `sandbox_required` — Whether this tool must run in a sandbox.

### Tool Execution Record

Logs a single tool execution.

**Fields:**

- `id` — Unique identifier (UUID).
- `tool` — Which tool was used.
- `action` — What action was performed.
- `parameters` — Input parameters (encrypted for sensitive data).
- `result_summary` — Brief description of the outcome.
- `success` — Whether the execution succeeded.
- `execution_time` — How long the execution took.
- `permission_id` — Which permission authorized this execution.
- `audit_log_id` — Link to the corresponding audit log entry.
- `created_at` — When the execution occurred.

### Tool Composition Record

Defines a multi-step tool workflow.

**Fields:**

- `id` — Unique identifier (UUID).
- `name` — Human-readable name for the workflow.
- `steps` — Ordered list of tool actions (encrypted JSON).
- `parameters` — Input parameters for the workflow.
- `created_at` — When the workflow was defined.
- `last_executed` — When it was last run.

---

## API Design

### Tool Gateway Endpoints

**List available tools**

- Method: GET
- Path: /tools
- Response: list of tools with name, description, actions, status

**Get tool details**

- Method: GET
- Path: /tools/{tool_name}
- Response: tool definition with all actions and their permission requirements

**Execute a tool action**

- Method: POST
- Path: /tools/{tool_name}/{action}
- Request body: action-specific parameters
- Response: execution result, execution_id
- Behavior: Checks permission, executes action, logs result, returns outcome.

**Check tool permission**

- Method: POST
- Path: /tools/{tool_name}/{action}/check
- Request body: action-specific parameters
- Response: permitted (boolean), reason (if denied)

### Filesystem Tool Endpoints

**Read a file**

- Method: POST
- Path: /tools/filesystem/read
- Request body: path (string), encoding (optional, default utf-8)
- Response: file content, file size, last modified timestamp
- Permission required: filesystem.read

**Write a file**

- Method: POST
- Path: /tools/filesystem/write
- Request body: path (string), content (string), mode (optional, default overwrite)
- Response: bytes written, success status
- Permission required: filesystem.write

**List directory**

- Method: POST
- Path: /tools/filesystem/list
- Request body: path (string), recursive (optional, default false)
- Response: list of files and directories with metadata
- Permission required: filesystem.list

**Search files**

- Method: POST
- Path: /tools/filesystem/search
- Request body: path (string), pattern (string), type (optional: file, directory, all)
- Response: list of matching files
- Permission required: filesystem.read

**Get file info**

- Method: POST
- Path: /tools/filesystem/info
- Request body: path (string)
- Response: file metadata (size, permissions, timestamps, type)
- Permission required: filesystem.read

**Delete a file**

- Method: POST
- Path: /tools/filesystem/delete
- Request body: path (string), recursive (optional, default false)
- Response: success status
- Permission required: filesystem.delete

### Terminal Tool Endpoints

**Execute a command**

- Method: POST
- Path: /tools/terminal/execute
- Request body: command (string), working_directory (optional), timeout (optional, default 30)
- Response: stdout, stderr, exit_code, execution_time
- Permission required: terminal.execute

**List running processes**

- Method: GET
- Path: /tools/terminal/processes
- Response: list of processes running in the sandbox
- Permission required: terminal.execute

**Interrupt a command**

- Method: POST
- Path: /tools/terminal/interrupt
- Request body: process_id (string)
- Response: success status
- Permission required: terminal.interrupt

### Browser Tool Endpoints

**Navigate to URL**

- Method: POST
- Path: /tools/browser/navigate
- Request body: url (string)
- Response: page title, page content (text), load time
- Permission required: browser.navigate

**Extract page content**

- Method: POST
- Path: /tools/browser/extract
- Request body: url (string), selector (optional, CSS selector)
- Response: extracted content, content type
- Permission required: browser.read

**Take screenshot**

- Method: POST
- Path: /tools/browser/screenshot
- Request body: url (string), width (optional), height (optional)
- Response: screenshot file path or base64-encoded image
- Permission required: browser.read

**Fill form**

- Method: POST
- Path: /tools/browser/form
- Request body: url (string), fields (dict of field names to values), submit (optional, default false)
- Response: form submission result
- Permission required: browser.interact

### Git Tool Endpoints

**Get repository status**

- Method: POST
- Path: /tools/git/status
- Request body: repository_path (string)
- Response: branch, modified files, staged files, untracked files
- Permission required: git.status

**Get diff**

- Method: POST
- Path: /tools/git/diff
- Request body: repository_path (string), ref (optional, commit or branch)
- Response: diff content
- Permission required: git.status

**Stage files**

- Method: POST
- Path: /tools/git/add
- Request body: repository_path (string), files (list of paths)
- Response: success status
- Permission required: git.add

**Create commit**

- Method: POST
- Path: /tools/git/commit
- Request body: repository_path (string), message (string), files (optional, list of paths to stage)
- Response: commit hash, commit message
- Permission required: git.commit

**Push to remote**

- Method: POST
- Path: /tools/git/push
- Request body: repository_path (string), remote (optional, default origin), branch (optional)
- Response: success status, remote URL
- Permission required: git.push

**Pull from remote**

- Method: POST
- Path: /tools/git/pull
- Request body: repository_path (string), remote (optional, default origin), branch (optional)
- Response: success status, changes pulled
- Permission required: git.pull

### Network Tool Endpoints

**Make HTTP request**

- Method: POST
- Path: /tools/network/request
- Request body: url (string), method (GET/POST/PUT/DELETE), headers (optional), body (optional), timeout (optional)
- Response: status_code, headers, body, response_time
- Permission required: network.http

**Download file**

- Method: POST
- Path: /tools/network/download
- Request body: url (string), destination (string), timeout (optional)
- Response: file size, download time, file path
- Permission required: network.download

**Upload file**

- Method: POST
- Path: /tools/network/upload
- Request body: url (string), file_path (string), headers (optional)
- Response: status_code, response body
- Permission required: network.upload

---

## Implementation Details

### Step 1: Tool Gateway

**Centralized tool management**

The Tool Gateway is the single entry point for all tool operations:

1. Receives tool requests from the AI
2. Validates the request format
3. Checks permissions via the Policy Engine
4. Routes to the appropriate tool
5. Collects the result
6. Logs to the Audit Logger
7. Returns the result to the AI

**Tool registration**

Each tool registers itself with the Gateway:
- Tool name and description
- Supported actions
- Permission requirements per action
- Trust level requirements
- Whether sandboxing is required

**Permission checking**

Before executing any action:
1. Identify the tool and action
2. Query the Policy Engine for permission
3. If permission is required but not granted, prompt the user
4. If permission is denied, return an error
5. If permission is granted, proceed with execution

**Error handling**

The Gateway handles errors consistently:
- Permission denied → clear error message explaining why
- Tool execution failed → error details without exposing sensitive information
- Timeout → notification and cleanup
- Tool unavailable → fallback or error message

### Step 2: Filesystem Tool

**Path validation**

The Filesystem Tool enforces path restrictions:
1. Only access paths within allowed directories (configured per permission)
2. Block access to sensitive system paths
3. Resolve symlinks and check the real path
4. Prevent path traversal attacks (../)
5. Validate file extensions for write operations

**Read operations**

Reading files:
1. Validate the path is allowed
2. Check filesystem.read permission
3. Read the file with the specified encoding
4. Return content, size, and metadata
5. Log the operation

**Write operations**

Writing files:
1. Validate the path is allowed
2. Check filesystem.write permission
3. If the file exists, check if overwrite is allowed
4. Create parent directories if needed
5. Write the content
6. Return bytes written and success status
7. Log the operation

**Search operations**

Searching for files:
1. Validate the search root path
2. Check filesystem.read permission
3. Use glob patterns or recursive directory walking
4. Return matching files with metadata
5. Log the operation

**Safe operations**

The Filesystem Tool should never:
- Follow symlinks outside allowed directories
- Open files with executable permissions
- Access /etc, /sys, /proc, or other system directories
- Modify files outside the configured workspace

### Step 3: Terminal Tool

**Sandbox execution**

All terminal commands run inside a Docker container:

Container setup:
- Minimal Linux image (Alpine or Python slim)
- Read-only root filesystem
- Writable work directory (mounted from host)
- Resource limits (CPU, memory, disk, network)
- Seccomp profile for additional restrictions

**Command execution**

When a command is executed:
1. Validate the command (check for obviously dangerous patterns)
2. Check terminal.execute permission
3. Start or reuse the sandbox container
4. Execute the command inside the container
5. Capture stdout, stderr, and exit code
6. Return results to the Tool Gateway
7. Log the command and result

**Command validation**

Before execution, validate the command:
- Block known dangerous patterns (rm -rf /, dd, etc.)
- Check for network access (requires separate permission)
- Check for file system modifications outside work directory
- Limit command length
- Limit output size

**Timeout handling**

Commands have a configurable timeout (default: 30 seconds):
- If the command doesn't complete within the timeout, it's killed
- The partial output is returned
- The timeout is logged
- The AI is informed that the command timed out

**Interactive commands**

Some commands require interaction (e.g., git push with authentication):
- Not supported in Phase 4 (non-interactive only)
- Interactive operations should be done by the user directly
- Future phases may add limited interaction support

### Step 4: Browser Tool

**Web page fetching**

Navigate to a URL and extract content:
1. Validate the URL (no file://, no internal network addresses)
2. Check browser.navigate permission
3. Use a headless browser (Playwright) to load the page
4. Wait for the page to load (with timeout)
5. Extract the page title and text content
6. Return the results

**Content extraction**

Extract useful content from web pages:
1. Parse the HTML
2. Extract main content (skip navigation, headers, footers, ads)
3. Use readability algorithms to identify the main article
4. Convert to clean text or markdown
5. Return the extracted content

**Screenshot capture**

Take screenshots of web pages:
1. Navigate to the URL
2. Wait for the page to load
3. Capture a screenshot at the specified resolution
4. Return the screenshot as a file or base64-encoded image

**Form interaction**

Fill and submit web forms (requires browser.interact permission):
1. Navigate to the form page
2. Identify form fields by name, ID, or CSS selector
3. Fill in the specified values
4. Optionally submit the form
5. Return the result page

**Security considerations**

The Browser Tool should:
- Never store cookies or credentials between sessions
- Block pop-ups and redirects by default
- Validate URLs before navigating (no javascript: URLs, no data: URLs)
- Treat all web content as T0 (untrusted)
- Apply prompt injection defense to extracted content

### Step 5: Git Tool

**Repository access**

The Git Tool operates on local git repositories:
1. Validate the repository path exists and is a git repository
2. Check git.status permission
3. Execute git commands using a subprocess
4. Parse and return structured results

**Read operations**

Reading git state:
- Status: modified files, staged files, untracked files
- Diff: changes in working directory or between commits
- Log: recent commit history
- Branch: current branch and available branches

**Write operations**

Modifying git state:
- Add: stage files for commit
- Commit: create a new commit with a message
- Branch: create or switch branches

Each write operation requires explicit permission:
- git.add: requires filesystem.write (you're modifying the staging area)
- git.commit: requires git.commit permission
- git.push: requires git.push permission (most sensitive — changes remote)

**Push protection**

Git push is the most dangerous git operation because it changes the remote repository:
- Always requires explicit permission
- Shows what will be pushed before executing
- Asks for confirmation
- Logs the push with remote URL and branch

**Repository validation**

Before operating on a repository:
- Check that the path is a valid git repository
- Check that the repository is in a known workspace
- Block operations on repositories outside allowed directories

### Step 6: Network Tool

**HTTP requests**

Make HTTP requests to external services:
1. Validate the URL (no internal addresses, no file:// URLs)
2. Check network.http permission
3. Set appropriate headers (User-Agent, Accept, etc.)
4. Make the request with timeout
5. Return status code, headers, and body

**Rate limiting**

Implement rate limiting for outbound requests:
- Default: 10 requests per minute per domain
- Configurable per domain
- Track request counts
- Delay or block requests that exceed limits

**Download management**

Download files from the internet:
1. Validate the URL
2. Check network.download permission
3. Stream the download to the specified destination
4. Report progress
5. Verify the download completed successfully
6. Log the download

**URL validation**

Before making any network request:
- Block requests to internal/private IP addresses (127.0.0.0/8, 10.0.0.0/8, 192.168.0.0/16, etc.)
- Block requests to file:// URLs
- Block requests to data: URLs
- Validate the URL format
- Check against a blocklist of known malicious domains (optional)

**Content classification**

Network responses are classified by trust level:
- Responses from known, trusted domains: T1
- Responses from unknown domains: T0
- API responses from configured services: T1
- All other responses: T0

### Step 7: Tool Composition

**Multi-step workflows**

The Tool Composition Engine allows chaining multiple tool actions:

Example: "Update the README with today's research findings"
1. Filesystem.read: Read current README
2. Research.get_daily: Get today's briefing
3. Filesystem.write: Update README with briefing
4. Git.add: Stage the changes
5. Git.commit: Commit with descriptive message

**Composition definition**

Workflows are defined as ordered lists of steps:
- Each step specifies: tool, action, parameters
- Parameters can reference outputs from previous steps
- Steps can have conditional execution (if/then)
- Steps can have error handling (retry, skip, abort)

**Execution engine**

The Composition Engine executes workflows:
1. Load the workflow definition
2. Execute each step in order
3. Pass outputs between steps as needed
4. Handle errors according to the workflow definition
5. Log the entire workflow execution
6. Return the final result

**Workflow storage**

Frequently used workflows can be saved:
- Store workflow definitions in the database
- Allow the AI to create and save workflows
- Provide a library of common workflows
- Allow manual triggering of saved workflows

---

## Dependencies

### New Dependencies for Phase 4

- **playwright** — Headless browser for web automation
- **gitpython** or **pygit2** — Git operations (or use subprocess with git CLI)
- **httpx** — Async HTTP client for network requests
- **aiofiles** — Async file operations

### Existing Dependencies Used

- **docker** — Sandbox management (from Phase 3)
- **SQLAlchemy** — New models for tool definitions and executions
- **FastAPI** — New tool endpoints

---

## Testing

### Unit Tests

**Filesystem tool tests**
- Test reading files within allowed directories
- Test that reading outside allowed directories is blocked
- Test writing files with permission
- Test that writing without permission is blocked
- Test file search functionality
- Test path traversal prevention

**Terminal tool tests**
- Test command execution in sandbox
- Test resource limits (CPU, memory, timeout)
- Test that dangerous commands are blocked
- Test stdout/stderr capture
- Test timeout handling

**Browser tool tests**
- Test page navigation and content extraction
- Test that javascript: URLs are blocked
- Test form filling
- Test screenshot capture
- Test that internal network addresses are blocked

**Git tool tests**
- Test status reading
- Test diff output
- Test staging and committing
- Test that push requires explicit permission
- Test repository validation

**Network tool tests**
- Test HTTP requests
- Test rate limiting
- Test that internal addresses are blocked
- Test download functionality

**Tool gateway tests**
- Test permission checking flow
- Test tool routing
- Test error handling
- Test audit logging

### Integration Tests

**End-to-end tool flow**
- AI requests file read → permission check → file read → audit log
- AI requests terminal command → permission check → sandbox execution → audit log
- AI requests git push → permission check → confirmation → push → audit log

**Tool composition tests**
- Execute a multi-step workflow
- Verify each step completes successfully
- Verify outputs are passed between steps
- Verify errors are handled correctly

### Manual Testing

After Phase 4 is complete:
- Ask MYSTI to read a file (should work with permission)
- Ask MYSTI to write a file (should require permission)
- Ask MYSTI to run a terminal command (should execute in sandbox)
- Ask MYSTI to browse a web page (should extract content)
- Ask MYSTI to check git status (should work with permission)
- Ask MYSTI to push to git (should require explicit confirmation)

---

## Edge Cases

### File Locking

If a file is locked by another process:
- Attempt to read anyway (most locks are advisory on Windows)
- If the file can't be read, return an error
- Log the locking conflict

### Sandbox Resource Exhaustion

If the sandbox runs out of resources:
- Kill the offending process
- Return a resource limit error
- Log the event
- Consider increasing limits if this happens frequently

### Browser Timeout

If a web page takes too long to load:
- Set a reasonable timeout (30 seconds)
- Return partial content if available
- Log the timeout
- Inform the user

### Git Conflicts

If a git operation would cause a conflict:
- Detect the conflict before executing
- Inform the AI and user
- Suggest resolution strategies
- Don't force the operation

### Network Timeouts

If an HTTP request times out:
- Return a timeout error
- Log the timeout
- Suggest retrying

---

## Deliverables

When Phase 4 is complete, you will have:

1. **Filesystem tool** — Secure file operations within allowed directories.

2. **Terminal tool** — Sandboxed command execution with resource limits.

3. **Browser tool** — Web page navigation, content extraction, and screenshots.

4. **Git tool** — Repository operations with permission gates on dangerous actions.

5. **Network tool** — HTTP requests with rate limiting and URL validation.

6. **Tool gateway** — Centralized orchestration, permission checking, and logging.

7. **Tool composition** — Multi-step workflow execution engine.

---

## What Comes Next

After Phase 4, you will move to **Phase 5: Memory + Research Integration**, which adds:
- Knowledge graph connecting memories, research, and people
- Context injection for conversations
- Learning tracker for skill development
- Project tracker for ongoing work
- Goal system for alignment checking

Phase 4's tools will be directly useful in Phase 5 — the filesystem tool can read project files, the git tool can track project changes, and the research tool can feed into the knowledge graph.

---

*Phase 4 gives MYSTI the ability to interact with your world, safely and with your permission.*
