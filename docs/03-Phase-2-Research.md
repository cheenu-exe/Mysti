# Phase 2: Research Agent

## Phase Overview

Phase 2 transforms MYSTI from a personal memory system into a proactive research companion. While Phases 0 and 1 focused on storing and retrieving your own information, Phase 2 adds the ability to continuously gather, evaluate, and present information from the outside world.

The Research Agent monitors multiple sources — GitHub, arXiv, RSS feeds, Hacker News, and model registries — filtering and ranking everything it finds based on your specific interests. Instead of dumping a flood of unfiltered headlines on you, it delivers a curated daily briefing: the three to five items most worth your attention, with clear explanations of why they matter to you.

Phase 2 also introduces **on-demand deep research** — the ability to ask MYSTI to investigate a topic thoroughly, gathering information from multiple sources, comparing perspectives, and producing a structured research report.

---

## Goals and Success Criteria

### Primary Goals

1. **Source integrations** — Connect to GitHub, arXiv, RSS/Atom feeds, Hacker News, and model registries.
2. **Research scheduler** — Automatically fetch and process new content on configurable schedules.
3. **Relevance engine** — Score and filter external content based on your interests and current projects.
4. **Deduplication** — Detect and merge the same item discovered from multiple sources.
5. **Daily briefing** — Generate a concise morning report of the most important items.
6. **Deep research** — On-demand investigation of specific topics with multi-source aggregation.
7. **Research database** — Store, search, and manage research findings.

### Success Criteria

You know Phase 2 is complete when:

- MYSTI automatically discovers relevant AI/tech developments without you searching for them
- Daily briefings contain items you actually find valuable, not noise
- The same item from different sources is detected and merged
- You can ask MYSTI to research a topic and get a structured report
- Research findings are searchable and linked to your memory system
- The research process runs automatically in the background

---

## Architecture

### What Phase 2 Adds

Phase 2 adds the research subsystem to the existing MYSTI infrastructure:

```
Existing Components:
├── CLI Interface
├── Memory Service (with semantic search, remote storage)
├── Encryption Layer
├── Key Management
├── Local RAM Cache
└── Embedding Service

Phase 2 Adds:
├── Research Scheduler (cron-like task runner)
├── Source Connectors (GitHub, arXiv, RSS, HN, etc.)
├── Collector (fetches and parses content)
├── Relevance Engine (scores items against your interests)
├── Deduplicator (detects duplicates across sources)
├── Daily Briefing Generator (morning report)
├── Deep Research Engine (on-demand investigation)
├── Research Database (remote encrypted storage)
└── Notification Service (delivers briefings)
```

### Data Flow for Automatic Research

```
Scheduler triggers source check (e.g., daily at 06:00)
    ↓
Source Connector fetches new items from configured sources
    ↓
Collector parses and normalizes items
    ↓
Deduplicator checks for existing items
    ↓
Relevance Engine scores each item against your interests
    ↓
Items above threshold encrypted locally
    ↓
Encrypted research items uploaded to remote storage
    ↓
Daily Briefing Generator selects top items
    ↓
Briefing delivered via notification (CLI, file, or email)
```

### Data Flow for Deep Research

```
You ask: "Research PQC migration strategies"
    ↓
Deep Research Engine parses the request
    ↓
Identifies relevant sources and search terms
    ↓
Fan-out to multiple sources in parallel
    ↓
Collect and parse results
    ↓
Relevance Engine scores each result
    ↓
Aggregate findings into structured report
    ↓
Store report in Research Database
    ↓
Report delivered to you
```

---

## Data Models

### Research Item Record

Stores a single piece of research content.

**Fields:**

- `id` — Unique identifier (UUID).
- `source` — Where this item came from (github, arxiv, rss, hackernews, web).
- `source_id` — The item's ID in the source system (e.g., GitHub repo full name, arXiv paper ID).
- `title` — Item title.
- `url` — Link to the original content.
- `encrypted_summary` — AI-generated summary of the item, encrypted.
- `encrypted_content` — Full content or description, encrypted.
- `relevance_score` — How relevant this item is to your interests (0.0-1.0).
- `relevance_reason` — Explanation of why this item scored as it did.
- `tags` — Topic tags for categorization (encrypted JSON array).
- `published_at` — When the item was originally published.
- `fetched_at` — When MYSTI discovered it.
- `read` — Whether you've viewed this item.
- `bookmarked` — Whether you've marked it as important.
- `category` — Research category (ai_models, cybersecurity, tools, papers, news).
- `remote_path` — The path/key in remote storage where the encrypted blob is stored.

### Research Source Record

Configuration for a research source.

**Fields:**

- `id` — Unique identifier.
- `name` — Human-readable source name.
- `type` — Source type (github, arxiv, rss, hackernews, custom).
- `config` — Source-specific configuration (encrypted JSON):
  - For GitHub: repositories to watch, topics, trending settings
  - For arXiv: search queries, categories, authors
  - For RSS: feed URLs, update frequency
  - For Hacker News: score thresholds, topics
- `enabled` — Whether this source is active.
- `last_fetched` — When this source was last checked.
- `fetch_interval` — How often to check (in seconds).
- `created_at` — When the source was added.

### Daily Briefing Record

Stores a generated daily briefing.

**Fields:**

- `id` — Unique identifier.
- `date` — The date this briefing covers.
- `encrypted_summary` — The briefing content, encrypted.
- `item_count` — Number of items included.
- `total_items_found` — Total items discovered before filtering.
- `created_at` — When the briefing was generated.
- `read` — Whether you've viewed the briefing.

### Deep Research Record

Stores the results of an on-demand research request.

**Fields:**

- `id` — Unique identifier.
- `query` — The original research question.
- `encrypted_report` — The full research report, encrypted.
- `sources_consulted` — List of sources that contributed.
- `item_count` — Number of sources/items analyzed.
- `confidence` — How confident MYSTI is in the report (low, medium, high).
- `created_at` — When the research was completed.
- `follow_up_questions` — Suggested questions for further investigation.

### Interest Profile Record

Defines your interests for relevance scoring.

**Fields:**

- `id` — Unique identifier.
- `topic` — Topic name (e.g., "cybersecurity", "PQC", "local LLMs").
- `keywords` — Associated keywords (encrypted JSON array).
- `weight` — Importance weight (0.0-1.0). Higher weight means more important.
- `projects` — Related project IDs (encrypted JSON array).
- `created_at` — When the interest was added.
- `updated_at` — When the interest was last updated.

---

## API Design

### Source Management Endpoints

**List sources**

- Method: GET
- Path: /research/sources
- Response: list of source configurations

**Add a source**

- Method: POST
- Path: /research/sources
- Request body: name, type, config (source-specific), fetch_interval
- Response: source details with ID
- Behavior: Validates configuration, tests connectivity, stores source.

**Update a source**

- Method: PUT
- Path: /research/sources/{source_id}
- Request body: fields to update
- Response: updated source details

**Remove a source**

- Method: DELETE
- Path: /research/sources/{source_id}
- Response: confirmation
- Behavior: Marks source as disabled (soft delete).

**Test a source**

- Method: POST
- Path: /research/sources/{source_id}/test
- Response: connectivity status, sample items
- Behavior: Fetches a small sample to verify the source works.

### Research Item Endpoints

**List research items**

- Method: GET
- Path: /research/items
- Query parameters: source (optional), category (optional), min_score (optional), unread_only (optional), limit (default 20), offset
- Response: list of research items with title, source, score, summary, published_at

**Get research item details**

- Method: GET
- Path: /research/items/{item_id}
- Response: full item details including content
- Behavior: Marks item as read.

**Bookmark an item**

- Method: POST
- Path: /research/items/{item_id}/bookmark
- Response: confirmation
- Behavior: Toggles bookmark status.

**Search research items**

- Method: POST
- Path: /research/search
- Request body: query (string), source (optional), category (optional), min_score (optional), limit (optional)
- Response: list of matching items with relevance scores
- Behavior: Uses hybrid search (semantic + keyword) from Phase 1.

### Daily Briefing Endpoints

**Get today's briefing**

- Method: GET
- Path: /research/briefing/today
- Response: briefing content or 404 if not yet generated

**Get briefing for date**

- Method: GET
- Path: /research/briefing/{date}
- Response: briefing content for the specified date

**Generate briefing manually**

- Method: POST
- Path: /research/briefing/generate
- Response: briefing content
- Behavior: Triggers immediate briefing generation.

**List all briefings**

- Method: GET
- Path: /research/briefing
- Query parameters: limit (default 30), offset
- Response: list of briefings with date, item_count, summary

### Deep Research Endpoints

**Start deep research**

- Method: POST
- Path: /research/deep
- Request body: query (string), depth (shallow, medium, deep), max_sources (optional)
- Response: research job ID
- Behavior: Starts a background research job.

**Get research status**

- Method: GET
- Path: /research/deep/{job_id}
- Response: job status (pending, running, completed, failed), progress

**Get research results**

- Method: GET
- Path: /research/deep/{job_id}/results
- Response: full research report or 404 if not complete

**List past research**

- Method: GET
- Path: /research/deep
- Query parameters: limit (default 20), offset
- Response: list of completed research reports with query, date, confidence

### Interest Profile Endpoints

**List interests**

- Method: GET
- Path: /research/interests
- Response: list of interest topics with weights and keywords

**Add an interest**

- Method: POST
- Path: /research/interests
- Request body: topic, keywords (array), weight, projects (optional)
- Response: interest details

**Update an interest**

- Method: PUT
- Path: /research/interests/{interest_id}
- Request body: fields to update
- Response: updated interest details

**Remove an interest**

- Method: DELETE
- Path: /research/interests/{interest_id}
- Response: confirmation

---

## Implementation Details

### Step 1: Research Scheduler

**Task scheduling framework**

Use APScheduler (Advanced Python Scheduler) to manage recurring research tasks. APScheduler provides:
- Cron-like scheduling (daily, hourly, weekly)
- One-time jobs for immediate execution
- Job persistence (survive restarts)
- Job stores (memory, database, Redis)
- Executors (thread, process, async)
- Missed job handling

**Job configuration**

Define jobs for each source:
- Source check job: runs at the configured interval for each source
- Briefing generation job: runs daily at a configurable time (default: 06:00)
- Consolidation job: runs weekly (from Phase 1)
- Deep research: triggered on-demand, not scheduled

**Job lifecycle**

Each job follows this pattern:
1. Acquire a lock (prevent overlapping runs)
2. Execute the source fetch or processing task
3. Update the source's last_fetched timestamp
4. Release the lock
5. Log the result (success, failure, items found)

**Error handling**

If a job fails:
- Log the error with full context
- Mark the source as having an error
- Continue with other jobs (don't let one failure block everything)
- Implement retry logic with exponential backoff
- Alert the user if a source fails repeatedly

### Step 2: Source Connectors

**GitHub connector**

Fetches information from GitHub:
- Trending repositories (daily, weekly)
- Repository releases (for watched repos)
- Topic-based discovery (search by topic)
- Star history changes (repos gaining stars)

Configuration:
- `repositories`: list of repo full names to watch (e.g., ["pytorch/pytorch", "huggingface/transformers"])
- `topics`: list of topics to search (e.g., ["llm", "cybersecurity", "local-ai"])
- `trending`: whether to fetch trending repos
- `trending_languages`: languages to track for trending

API endpoints used:
- GitHub REST API v3 for repository data
- GitHub Search API for topic-based discovery
- GitHub Trending (scraped, as there's no official API)

Rate limiting:
- Respect GitHub's rate limits (60 requests/hour for unauthenticated, 5000 for authenticated)
- Use conditional requests and ETags to reduce unnecessary calls
- Cache responses for the duration of the fetch interval

**arXiv connector**

Fetches academic papers from arXiv:
- Search by query (keywords, authors, categories)
- Recent papers in specified categories
- Papers by specific authors

Configuration:
- `queries`: list of search queries
- `categories`: list of arXiv categories (e.g., ["cs.CR", "cs.AI", "cs.LG"])
- `max_results`: maximum papers per fetch

API used:
- arXiv API (Atom feed format)
- No authentication required
- Rate limit: 1 request per 3 seconds

Parsing:
- Extract paper ID, title, authors, abstract, categories, published date
- Generate summary from abstract
- Score relevance based on your interest profile

**RSS/Atom connector**

Fetches content from any RSS or Atom feed:
- Blog posts
- News articles
- Documentation updates
- Release announcements

Configuration:
- `feeds`: list of feed URLs
- `categories`: optional categorization hints

Library:
- feedparser for RSS/Atom parsing
- Handle various feed formats and encodings
- Extract title, link, summary, published date, author

Rate limiting:
- Respect the feed's refresh interval if specified
- Default to the source's configured fetch interval
- Don't hammer small servers

**Hacker News connector**

Fetches stories from Hacker News:
- Top stories
- New stories
- Best stories
- Stories by score threshold

Configuration:
- `min_score`: minimum story score (default: 100)
- `topics`: optional topic filtering
- `max_stories`: maximum stories per fetch

API used:
- Hacker News Firebase API (no authentication)
- Fetch story IDs, then individual story details
- Rate limiting: be gentle, no official limits but don't be aggressive

**Model registry connector**

Monitors AI model releases and benchmarks:
- Hugging Face trending models
- Open LLM Leaderboard updates
- New model releases from major providers
- Benchmark result changes

Configuration:
- `track_models`: list of model families to track
- `track_providers`: list of providers (Hugging Face, OpenAI, Anthropic, etc.)
- `benchmark_threshold`: minimum benchmark improvement to report

Sources:
- Hugging Face API
- Open LLM Leaderboard (web scraping or API if available)
- Provider announcement feeds

### Step 3: Collector

**Content normalization**

The Collector takes raw content from various sources and normalizes it into a consistent format:

For each item:
1. Extract title, URL, published date, and content
2. Clean and normalize text (remove HTML, fix encoding)
3. Generate a summary (either from the source or using LLM)
4. Extract or assign category tags
5. Assign a unique source ID for deduplication

**Content extraction**

For different source types:
- GitHub: Extract repo description, README (first 1000 chars), language, stars, topics
- arXiv: Extract title, abstract, authors, categories
- RSS: Extract full article content or summary
- Hacker News: Extract title, URL, score, comment count, discussion URL
- Web: Extract main content, skip navigation and ads

**LLM-assisted summarization**

For items that need summarization:
1. Prepare the raw content (truncate if too long)
2. Send to LLM with a summarization prompt
3. Parse the response into structured fields
4. Store the summary alongside the raw content

Summarization prompt template:
- "Summarize the following [type] in 2-3 sentences. Focus on what's new, important, or different. Include any key numbers, dates, or technical details."

### Step 4: Relevance Engine

**Interest profile**

The Relevance Engine uses your interest profile to score items:

Your interests are defined as:
- Topics (e.g., "cybersecurity", "local LLMs", "DevSecOps")
- Keywords associated with each topic
- Weight/importance for each topic
- Related projects

The interest profile can be:
- Manually configured (you add topics and keywords)
- Auto-discovered from your memory (extract topics from stored memories)
- A combination of both

**Scoring approach**

For each research item:
1. Extract keywords and topics from the item
2. Compare against your interest profile
3. Calculate a weighted relevance score:
   - Keyword match score (how many of your keywords appear)
   - Topic match score (how closely the item's topics align with yours)
   - Recency score (newer items score higher)
   - Source credibility score (some sources are more reliable)
4. Generate a relevance explanation ("This item matches your interest in [topic] because [reason]")

**Relevance thresholds**

- Score > 0.7: High relevance — definitely include in briefing
- Score 0.4-0.7: Medium relevance — include if space allows
- Score < 0.4: Low relevance — don't include in briefing, but store for search

**Adaptive scoring**

Over time, the Relevance Engine can learn from your behavior:
- Items you bookmark → increase weight for similar topics
- Items you skip → decrease weight for similar topics
- This creates a feedback loop that improves relevance over time

### Step 5: Deduplicator

**Duplicate detection**

The same information often appears from multiple sources:
- A new model release appears on GitHub, Hacker News, and Twitter
- A paper appears on arXiv and is discussed on Hacker News
- A blog post is shared via RSS and appears in web search

The Deduplicator detects these cases:
1. Compare new items against recent items in the research database
2. Use multiple signals for deduplication:
   - URL similarity (same or similar URLs)
   - Title similarity (fuzzy string matching)
   - Content similarity (semantic similarity using embeddings)
   - Source ID matching (same GitHub repo, same arXiv paper)
3. When duplicates are found, merge them:
   - Keep the most detailed version
   - Combine tags from all versions
   - Use the highest relevance score
   - Track all sources (so you know where you found it)

**Deduplication threshold**

- Exact match (same URL or source ID): definitely duplicate
- High similarity (title similarity > 0.9, content similarity > 0.8): likely duplicate
- Medium similarity (title similarity > 0.7, content similarity > 0.6): possibly duplicate, flag for review

### Step 6: Daily Briefing Generator

**Briefing format**

The daily briefing is a concise report delivered each morning:

```
MYSTI Daily Briefing — August 31, 2026

Found 47 items across 5 sources today. Here are the top 5:

1. [HIGH RELEVANCE] New Local LLM Release: Phi-3.5
   Source: GitHub/Hugging Face
   Why it matters: You're tracking local LLMs for your MYSTI project.
   Summary: Microsoft released Phi-3.5 with improved coding and reasoning.
   Benchmark scores show 15% improvement over Phi-3 on HumanEval.
   Link: [url]

2. [HIGH RELEVANCE] Nmap 7.96 Released
   Source: RSS (SecurityTools)
   Why it matters: You use Nmap in your cybersecurity work.
   Summary: New version adds improved script engine and faster scans.
   Link: [url]

3. [MEDIUM RELEVANCE] FastAPI 0.112.0
   Source: GitHub
   Why it matters: You use FastAPI for backend development.
   Summary: Adds WebSocket improvements and dependency injection changes.
   Link: [url]

4. [MEDIUM RELEVANCE] New Paper: Efficient PQC Migration Strategies
   Source: arXiv
   Why it matters: You're interested in post-quantum cryptography.
   Summary: Proposes a phased approach to PQC migration for enterprise systems.
   Link: [url]

5. [MEDIUM RELEVANCE] Docker Desktop 4.35 Beta
   Source: Hacker News
   Why it matters: You use Docker for development and sandboxing.
   Summary: Adds GPU passthrough improvements and WSL2 integration fixes.
   Link: [url]

---
47 items discovered, 12 relevant, 5 featured.
Next briefing: Tomorrow at 06:00
```

**Briefing generation process**

1. Collect all new items from the past 24 hours
2. Filter by relevance score (minimum threshold)
3. Rank by relevance score
4. Select top N items (configurable, default 5)
5. For each item, generate a one-line summary and relevance explanation
6. Format into the briefing template
7. Store the briefing in the database
8. Deliver via notification

**Briefing delivery**

Briefings can be delivered through:
- CLI notification (display when MYSTI starts)
- File output (save to a markdown file)
- Email (if configured)
- Desktop notification (Phase 7)

### Step 7: Deep Research Engine

**Research request parsing**

When you ask MYSTI to research a topic:
1. Parse the query to understand the research question
2. Identify key concepts and search terms
3. Determine the scope (shallow, medium, deep)
4. Estimate the number of sources to consult

**Multi-source investigation**

The Deep Research Engine fans out to multiple sources in parallel:
1. Generate search queries for each source type
2. Fetch results from GitHub, arXiv, RSS, web search
3. Collect and normalize all results
4. Score relevance of each result
5. Filter to the most relevant sources

**Report generation**

Compile findings into a structured report:
1. Executive summary (2-3 sentences)
2. Key findings (5-10 bullet points)
3. Detailed analysis (organized by subtopic)
4. Sources consulted (with links)
5. Confidence assessment (how complete is this research?)
6. Suggested follow-up questions

**Research depth levels**

- **Shallow:** Quick scan of 5-10 sources, executive summary only
- **Medium:** Thorough scan of 10-20 sources, key findings with some detail
- **Deep:** Comprehensive scan of 20-50 sources, full analysis with comparisons

### Step 8: Research Database

**Storage**

All research items are stored in remote encrypted storage with:
- Encrypted content (summaries and full content)
- Metadata (source, score, tags, dates)
- Relationships (deduplication links, related items)
- Remote paths for each encrypted blob

**Search**

Research items are searchable through:
- Keyword search
- Semantic search (using the same embedding infrastructure from Phase 1)
- Filter by source, category, score, date range, read status

**Retention**

Research items are retained based on a configurable policy:
- Default: keep all items indefinitely
- Option: auto-delete low-relevance items after 30 days
- Bookmarked items are always retained

---

## Dependencies

### New Dependencies for Phase 2

- **APScheduler** — Task scheduling
- **feedparser** — RSS/Atom feed parsing
- **httpx** — Async HTTP client (for API calls)
- **beautifulsoup4** — HTML parsing (for web scraping)
- **trafilatura** — Main content extraction from web pages
- **newspaper3k** or **readability-lxml** — Article extraction

### Existing Dependencies Used

- **sentence-transformers** — For embedding research items (from Phase 1)
- **FAISS** — For semantic search on research items (from Phase 1)
- **boto3** — Remote storage operations (from Phase 0)
- **cryptography** — Encrypting research content

---

## Testing

### Unit Tests

**Source connector tests**
- Test each source connector with mock API responses
- Test error handling (rate limits, network failures, malformed data)
- Test rate limiting behavior
- Test content normalization

**Relevance scoring tests**
- Test scoring with known interest profiles and test items
- Test that high-relevance items score above threshold
- Test that low-relevance items score below threshold
- Test explanation generation

**Deduplication tests**
- Test exact match detection (same URL)
- Test fuzzy match detection (similar titles)
- Test semantic match detection (same content, different wording)
- Test merging of duplicate items

**Briefing generation tests**
- Test that briefings include the top N items
- Test that briefings are formatted correctly
- Test that briefings respect relevance thresholds

### Integration Tests

**End-to-end research flow**
- Configure a test source with known content
- Run a research cycle
- Verify items are collected, scored, and stored
- Generate a briefing and verify its content

**Multi-source deduplication**
- Add the same item to multiple sources
- Run a research cycle
- Verify duplicates are detected and merged

### Manual Testing

After Phase 2 is complete:
- Add a few RSS feeds you actually read
- Add some GitHub repos you follow
- Run MYSTI for a few days
- Check if the daily briefings are relevant
- Ask MYSTI to research a topic you're interested in
- Verify the research report is useful

---

## Edge Cases

### Source Unavailability

If a source is temporarily unavailable:
- Log the failure
- Skip that source for this cycle
- Try again at the next scheduled interval
- Alert the user if a source fails repeatedly (e.g., 3 consecutive failures)

### Rate Limiting

If a source rate-limits MYSTI:
- Respect the rate limit
- Back off exponentially
- Log the rate limit event
- Continue with other sources

### Content Too Large

If a fetched item is very large:
- Truncate to a reasonable size for processing
- Store a link to the full content rather than the full text
- Use summarization to extract key information

### Relevance Drift

If the Relevance Engine starts returning irrelevant results:
- Allow manual adjustment of interest weights
- Provide a "not relevant" feedback mechanism
- Periodically recalibrate based on feedback

### Research Cost

LLM-based summarization and relevance scoring can be expensive:
- Use local models when possible
- Batch similar operations to reduce API calls
- Cache results to avoid reprocessing
- Provide cost estimates before running deep research

---

## Deliverables

When Phase 2 is complete, you will have:

1. **Source integrations** — Working connectors for GitHub, arXiv, RSS, Hacker News, and model registries.

2. **Research scheduler** — Automatic, recurring research tasks with configurable intervals.

3. **Relevance engine** — Scores and filters items based on your interests.

4. **Deduplication** — Detects and merges the same item from multiple sources.

5. **Daily briefing** — A concise morning report of the most important items.

6. **Deep research** — On-demand investigation with multi-source aggregation.

7. **Research database** — Remote encrypted storage for research findings.

8. **Interest profile** — Configurable topics and weights for relevance scoring.

---

## What Comes Next

After Phase 2, you will move to **Phase 3: Policy Engine + Security**, which adds:
- Permission system for controlling AI access to your system
- Trust levels for different types of content and actions
- Mode control (Passive/Active)
- Audit logging for accountability
- Sandbox management for safe execution

Phase 2's research capabilities will be used in Phase 3 to ensure that external content (from research) is treated as untrusted and doesn't inject instructions into the AI.

---

*Phase 2 makes MYSTI a proactive research companion that discovers what matters to you.*
