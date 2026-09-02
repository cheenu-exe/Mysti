# MYSTI — Personal AI Operating Layer

## Project Overview

MYSTI is a private, encrypted personal AI agent that continuously learns about you, researches developments relevant to your interests, maintains a secure knowledge base, and can optionally operate your machine with strict permission controls.

Unlike a generic chatbot, MYSTI is designed to be **your** AI — it knows your preferences, remembers your conversations, tracks your projects, researches topics you care about, and follows a security model that keeps you in control at all times.

The name "MYSTI" is derived from the handle "mysti" — a personal identity marker that reflects the project's nature as a deeply personal system.

---

## Core Philosophy

MYSTI is built on four foundational principles:

**1. Privacy by Design**
Everything about you is encrypted at rest. The AI never has direct access to encryption keys. Your data is encrypted locally on your Arch machine before being sent to remote storage. The remote provider never sees plaintext. The master key never leaves your trusted device.

**2. Permission Before Action**
The AI cannot autonomously decide to access your system. A security layer gates every action. You explicitly grant permissions, and every action is audited.

**3. Passive by Default**
MYSTI's default state is to think, research, and suggest — not to execute. It only gains the ability to act on your machine when you explicitly switch to Active Mode.

**4. Depth Over Breadth**
MYSTI is designed to become deeply knowledgeable about the areas you care about, rather than superficially aware of everything. Quality of information matters more than quantity.

---

## What MYSTI Is Not

MYSTI is not:

- A cloud service that stores your plaintext data on someone else's server
- A chatbot that forgets everything between sessions
- An autonomous agent that can do whatever it wants
- A productivity tool that bombards you with notifications
- A replacement for your operating system
- A general-purpose assistant that tries to do everything

MYSTI is:

- A private, encrypted knowledge system with remote storage
- A research agent that curates information for you
- A memory layer that remembers what matters
- A sandboxed execution environment with strict permissions
- A personal AI that adapts to your specific needs over time

---

## High-Level Architecture

MYSTI operates as a **remote-memory, local-cache system**. Persistent personal memory lives remotely in encrypted form. The local Arch machine holds only a small temporary cache. The decryption key never leaves your trusted device.

### Architecture Constraint

> **MYSTI shall operate as a remote-memory, local-cache system. Persistent user memory shall be stored remotely only in client-side encrypted form. Plaintext personal memory shall exist locally only transiently during authorized retrieval/use. The master decryption key shall remain exclusively within the user's trusted device and shall never be transmitted to the AI server, storage provider, or third-party model provider.**

```
              YOUR ARCH MACHINE
┌──────────────────────────────────────────────┐
│                                              │
│              MYSTI AI Agent                  │
│                    │                         │
│             ┌──────▼──────┐                  │
│             │ Memory Mgr  │                  │
│             └──────┬──────┘                  │
│                    │                         │
│           ┌────────▼────────┐                │
│           │ Tiny RAM Cache  │                │
│           │ 100-256 MB max  │                │
│           │ TTL / LRU       │                │
│           │ encrypted       │                │
│           └────────┬────────┘                │
│                    │                         │
│              cache miss                      │
│                    │                         │
│          🔑 Key Manager                      │
│          (master key NEVER uploaded)         │
│                    │                         │
└────────────────────┼─────────────────────────┘
                     │
              encrypted HTTPS
                     │
                     ▼
┌──────────────────────────────────────────────┐
│         REMOTE OBJECT STORAGE                │
│                                              │
│  ████████████████████████████████████████    │
│  ███ ENCRYPTED MEMORY ARCHIVE ██████████    │
│  ████████████████████████████████████████    │
│                                              │
│       Provider sees ciphertext only          │
│       No decryption key                     │
│       No plaintext                          │
└──────────────────────────────────────────────┘
```

---

## Subsystem Breakdown

### 1. User Interface Layer

This is how you interact with MYSTI. It can take multiple forms:

- **CLI (Command Line Interface)** — The simplest form. A terminal-based chat where you type commands and the AI responds. This is the first interface that will be built.
- **Web Dashboard** — A browser-based interface with a chat panel, memory browser, research feed, and security controls. Built with Next.js and React.
- **Voice Interface** — Speech-to-text input and text-to-speech output using your cloned voice (Coqui TTS XTTS v2). Added in Phase 8.

The UI layer handles:
- Displaying conversations
- Collecting user input
- Showing system status (current mode, permissions, etc.)
- Providing controls for mode switching
- Rendering research reports and memory search results

### 2. Mode Control

MYSTI operates in one of two modes at any given time:

**Passive Mode (Default)**
The AI can read your encrypted memory, conduct research, analyze information, suggest plans, and prepare actions. It cannot execute anything on your system. This is the safe, always-available state.

**Active Mode (Opt-in)**
You explicitly switch to Active Mode when you want the AI to take actions on your computer. Even in Active Mode, every action requires permission according to the policy engine. Active Mode sessions can have time limits for added safety.

The mode switch is a deliberate user action, not something the AI can trigger itself.

### 3. Passive Agent

The Passive Agent handles all intelligence work that doesn't require system access:

- Research and information gathering
- Analysis of papers, releases, and projects
- Memory retrieval and consolidation
- Planning and suggestion generation
- Report creation
- Context preparation for conversations

This agent has access to:
- Your encrypted memory (through the Memory Service)
- The research sources (web, RSS, arXiv, GitHub)
- The AI models (for reasoning and analysis)

It does not have access to:
- Your filesystem
- Your terminal
- Your browser
- Your network (beyond research sources)
- Your applications

### 4. Active Agent

The Active Agent extends the Passive Agent's capabilities with system access:

- Filesystem operations (read, write, delete with permission)
- Terminal execution (sandboxed in Docker)
- Browser automation (headless browser)
- Git operations (status, commit, push with permission)
- Application launching
- Network requests (with restrictions)

Every action the Active Agent takes goes through the Policy Engine first. If permission is not granted, the action is blocked and logged.

### 5. Policy Engine

The Policy Engine is the security core of MYSTI. It controls:

- What actions are permitted in each mode
- Which resources can be accessed
- How long permissions last
- What trust level is required for each action
- Whether an action is allowed, requires approval, or is blocked

The Policy Engine enforces a trust level system:

| Level | Name | Description | Examples |
|-------|------|-------------|----------|
| T0 | Untrusted | External content from unknown sources | Web pages, emails, downloaded files |
| T1 | Research | Information gathered through research agents | Articles, papers, model comparisons |
| T2 | Personal | Your encrypted memory and preferences | Your profile, projects, relationships |
| T3 | Local Tools | Your filesystem, terminal, applications | Your code, documents, configurations |
| T4 | Sensitive | Credentials, secrets, financial data | API keys, passwords, tokens |
| T5 | Administrative | OS-level changes, system configuration | Installing software, modifying system files |

Actions cannot automatically escalate trust levels. If the AI needs to perform an action at a higher trust level, it must request explicit user approval.

### 6. Memory Service

The Memory Service manages all persistent data about you using a **remote-memory, local-cache architecture**:

- **Remote Encrypted Storage** — All persistent data is encrypted locally using AES-256-GCM before being sent to remote object storage. The remote provider never receives plaintext. The master key never leaves your Arch machine.
- **Local Ephemeral Cache** — A small RAM-only cache (100-256 MB) holds recently accessed memories with TTL/LRU expiration. Cache disappears on machine shutdown. No permanent plaintext memory on the local device.
- **Key Hierarchy** — A master key (stored in OS keystore, never uploaded) protects category-specific keys, which protect individual records. Compromising one category doesn't expose others.
- **Semantic Search** — Vector embeddings enable searching by meaning, not just keywords. Search metadata is stored remotely in encrypted form.
- **Memory Levels** — Different types of information have different access rules (temporary, short-term, persistent, sensitive, secrets).
- **Consolidation** — Periodic merging of related records, extraction of key facts, and contradiction detection.
- **Pluggable Storage Backend** — The storage interface is abstract, allowing you to swap between S3, Backblaze B2, Cloudflare R2, or any S3-compatible provider without rewriting MYSTI.

### 7. Research Agent

The Research Agent continuously gathers information from external sources:

- **GitHub** — Trending repositories, releases, topics you follow
- **arXiv** — Papers in AI, cybersecurity, systems, and related fields
- **RSS/Atom Feeds** — Blogs, news sites, and documentation you track
- **Hacker News** — Top stories and discussions
- **Model Registries** — Hugging Face, Open LLM Leaderboard, model releases
- **Web Search** — On-demand deep research

Research findings are filtered for relevance to your interests, deduplicated, and stored in your knowledge base. A daily briefing summarizes the most important items.

### 8. Tool Layer

The Tool Layer provides the actual capabilities that the Active Agent can use:

- **Filesystem Tool** — Read, write, search, and manage files within allowed directories
- **Terminal Tool** — Execute commands in a sandboxed Docker container with resource limits
- **Browser Tool** — Navigate, screenshot, and extract content using a headless browser
- **Git Tool** — Repository operations with permission gates on destructive actions
- **Network Tool** — HTTP requests with rate limiting and URL validation
- **Application Tool** — Launch and interact with applications (with restrictions)

Each tool validates permissions before execution and logs all actions to the audit trail.

### 9. Security Layer

The Security Layer encompasses several cross-cutting concerns:

- **Audit Logging** — Every action, permission check, and decision is logged with timestamps, context, and outcomes.
- **Sandbox Manager** — Docker-based isolation for terminal execution with resource limits and network restrictions.
- **Prompt Injection Defense** — Content classification, instruction stripping, and separation of data from instructions.
- **Encryption Management** — Key generation, storage, rotation, and hierarchy management.
- **Backup and Recovery** — Encrypted backups with incremental strategy and recovery procedures.

---

## Data Flow

### Passive Mode Conversation

```
You ask a question
    ↓
UI sends to Passive Agent
    ↓
Passive Agent queries Memory Manager
    ↓
Memory Manager checks RAM cache
    ↓
    cache miss → query remote index → identify relevant encrypted objects
    ↓
Download only those encrypted objects
    ↓
Decrypt locally using master key (never leaves device)
    ↓
Temporarily store in RAM cache (TTL: 24h)
    ↓
Passive Agent loads relevant research (if applicable)
    ↓
Passive Agent sends context + question to LLM
    ↓
LLM generates response
    ↓
Response displayed to you
    ↓
Conversation encrypted and uploaded to remote storage
    ↓
RAM cache cleared of plaintext after use
```

### Active Mode Execution

```
You request an action ("write this file")
    ↓
UI sends to Active Agent
    ↓
Active Agent identifies required tool (Filesystem Tool)
    ↓
Active Agent checks current mode (Active)
    ↓
Policy Engine checks permission (filesystem.write = granted)
    ↓
Action executed in sandbox (if terminal) or directly (if filesystem)
    ↓
Result returned to Active Agent
    ↓
Audit log entry created
    ↓
Response displayed to you
```

### Research Cycle

```
Scheduler triggers research task (e.g., daily at 06:00)
    ↓
Research Agent fetches from configured sources
    ↓
Raw items collected (papers, repos, articles)
    ↓
Relevance Engine scores each item against your interests
    ↓
Items above threshold encrypted locally
    ↓
Encrypted research items uploaded to remote storage
    ↓
Duplicates filtered out
    ↓
Daily report generated (top 5 items)
    ↓
Report delivered to you via UI notification
```

---

## Technology Stack

### Backend
- **Language:** Python 3.11+
- **Web Framework:** FastAPI
- **Data Validation:** Pydantic
- **Task Scheduling:** APScheduler

### Storage
- **Primary Storage:** Remote object storage (S3-compatible)
- **Providers:** AWS S3, Backblaze B2, Cloudflare R2, MinIO (self-hosted)
- **Local Cache:** RAM-only (100-256 MB, TTL/LRU, encrypted)
- **Search Index:** Remote encrypted index (for metadata-based lookup)
- **Vector Store:** Remote encrypted embeddings (for semantic search)

### Security
- **Encryption:** AES-256-GCM (via cryptography library)
- **Key Storage:** OS keystore (master key NEVER uploaded)
- **Key Hierarchy:** Master key → category keys → record keys
- **Sandbox:** Docker with seccomp profiles
- **Authentication:** Local only (no external auth needed)

### AI/ML
- **LLM Integration:** LiteLLM (supports OpenAI, Anthropic, local models)
- **Embeddings:** sentence-transformers (local) or OpenAI embeddings
- **Model Management:** Ollama (local models)

### Frontend
- **Framework:** Next.js 14+ with React
- **Styling:** Tailwind CSS
- **UI Components:** shadcn/ui
- **State Management:** Zustand

### DevOps
- **Containerization:** Docker + Docker Compose
- **Version Control:** Git + GitHub
- **CI/CD:** GitHub Actions (optional)

---

## Project Structure

```
mysti/
│
├── core/
│   ├── agent.py              # Main agent logic
│   ├── planner.py            # Planning and reasoning
│   ├── router.py             # Model routing
│   └── scheduler.py          # Task scheduling
│
├── memory/
│   ├── manager.py            # Memory Manager (orchestrates cache + remote)
│   ├── cache.py              # Local RAM cache (TTL/LRU)
│   ├── encryption.py         # Encryption/decryption
│   ├── retrieval.py          # Search and retrieval
│   ├── consolidation.py      # Memory merging
│   └── policies.py           # Access control
│
├── storage/
│   ├── provider.py           # Abstract storage interface
│   ├── s3.py                 # S3/Backblaze/R2 implementation
│   ├── local.py              # Local development storage
│   └── index.py              # Remote search index
│
├── research/
│   ├── sources.py            # Source integrations
│   ├── collector.py          # Data collection
│   ├── relevance.py          # Relevance scoring
│   ├── evaluator.py          # Quality assessment
│   └── reporter.py           # Report generation
│
├── security/
│   ├── permissions.py        # Permission management
│   ├── key_manager.py        # Key management (master key NEVER uploaded)
│   ├── vault.py              # Key hierarchy
│   ├── sandbox.py            # Docker sandbox
│   ├── audit.py              # Audit logging
│   └── injection.py          # Prompt injection defense
│
├── tools/
│   ├── filesystem.py         # File operations
│   ├── terminal.py           # Command execution
│   ├── browser.py            # Web automation
│   ├── git.py                # Git operations
│   ├── network.py            # HTTP requests
│   └── gateway.py            # Tool orchestration
│
├── models/
│   ├── registry.py           # Model catalog
│   ├── router.py             # Model selection
│   ├── benchmark.py          # Performance testing
│   └── evaluator.py          # Quality metrics
│
├── api/
│   ├── server.py             # FastAPI application
│   ├── routes/               # API endpoints
│   └── middleware.py          # Security middleware
│
├── ui/
│   ├── dashboard/            # Next.js app
│   ├── components/           # React components
│   └── styles/               # CSS/Tailwind
│
├── config/
│   ├── settings.py           # Configuration
│   ├── permissions.yaml      # Permission definitions
│   └── sources.yaml          # Research sources
│
├── tests/                    # Test suite
├── docs/                     # Documentation
├── docker/                   # Docker configurations
├── scripts/                  # Utility scripts
└── pyproject.toml            # Project metadata
```

---

## Build Phases Summary

| Phase | Name | Duration | Focus |
|-------|------|----------|-------|
| 0 | Foundation | Weeks 1-3 | Project scaffold, remote storage, encryption, basic CLI |
| 1 | Memory Intelligence | Weeks 4-6 | Semantic search, consolidation, memory categories |
| 2 | Research Agent | Weeks 7-10 | Web research, relevance engine, daily briefings |
| 3 | Policy Engine + Security | Weeks 11-14 | Permissions, trust levels, audit, sandbox |
| 4 | Tool Integration | Weeks 15-18 | Filesystem, terminal, browser, git tools |
| 5 | Memory + Research Integration | Weeks 19-22 | Knowledge graph, context injection, learning tracker |
| 6 | Self-Improvement Loop | Weeks 23-26 | Model registry, benchmarks, update recommendations |
| 7 | User Interface | Weeks 27-30 | Dashboard, web UI, security panel |
| 8 | Advanced Features | Weeks 31-34 | Voice (cloned), multi-model routing, backup, PWA |

---

## Success Criteria

The project is successful when:

1. **You can have a conversation with MYSTI** and it remembers context from previous sessions, with all data encrypted at rest and stored remotely. Plaintext exists only transiently in RAM during use.

2. **MYSTI delivers daily research briefings** that are actually relevant to your interests, not just a dump of headlines.

3. **You can switch to Active Mode** and MYSTI can perform tasks on your machine with explicit permission gates and full audit logging.

4. **The security model actually works** — prompt injection attempts are caught, unauthorized actions are blocked, and every action is traceable. The master key never leaves your Arch machine.

5. **You trust it enough to leave it running** as a background service that researches and maintains your knowledge base without requiring constant attention.

6. **It saves you time** — you spend less time manually searching for AI news, less time remembering details from past conversations, and less time context-switching between tools.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Scope creep | Project never finishes | Strict phase boundaries, MVP-first approach |
| Security vulnerabilities | Data exposure | Defense in depth, audit everything, sandbox aggressively |
| LLM costs | Expensive to run | Local models for routine tasks, cloud for complex reasoning |
| Remote storage outage | Temporary memory access loss | Local cache for recent items, multiple provider support |
| Key loss | Permanent data loss | Offline key backup (you control), recovery procedures |
| Over-engineering | Too complex to maintain | Start simple, add complexity only when needed |
| Loss of interest | Project abandoned | Build something you'll actually use in Phase 0 |

---

## Getting Started

To begin building MYSTI:

1. **Read Phase 0 document** (01-Phase-0-Foundation.md) for detailed setup instructions
2. **Set up the development environment** (Python, Docker, Git on Arch Linux)
3. **Configure remote storage** (S3, Backblaze B2, or Cloudflare R2)
4. **Build the project scaffold** (FastAPI + encryption + storage interface)
5. **Implement encrypted memory storage** (encrypt locally, upload remotely)
6. **Create the basic CLI interface** (your first interaction with MYSTI)

Everything else builds on this foundation.

---

## Document Navigation

Each phase document follows a consistent structure:

1. **Phase Overview** — What this phase accomplishes
2. **Goals and Success Criteria** — How you know when it's done
3. **Architecture** — How this phase fits into the overall system
4. **Data Models** — Remote storage schemas and structures
5. **API Design** — Endpoints and interfaces
6. **Implementation Details** — Step-by-step build order
7. **Dependencies** — Libraries and tools needed
8. **Testing** — How to verify everything works
9. **Edge Cases** — What can go wrong and how to handle it
10. **Deliverables** — What you have when this phase is complete

---

*MYSTI — Your AI. Your Data. Your Rules.*
