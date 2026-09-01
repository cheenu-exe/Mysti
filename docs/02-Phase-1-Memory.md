# Phase 1: Memory Intelligence

## Phase Overview

Phase 1 transforms MYSTI's remote encrypted storage from a simple key-value store into an intelligent memory system. In Phase 0, you could store and retrieve encrypted records remotely. In Phase 1, those records become searchable by meaning, organized by category, and periodically consolidated to maintain coherence and reduce redundancy.

The core addition is **semantic search** — the ability to find relevant information not just by matching keywords, but by understanding the meaning behind your queries. When you ask "what do I know about Docker networking," the system should find records about Docker, networking, containers, and related topics, even if they don't contain the exact phrase "Docker networking."

Phase 1 also introduces **memory consolidation** — a background process that periodically reviews your stored memories, merges related records, extracts key facts, detects contradictions, and maintains an organized knowledge base.

Additionally, Phase 1 adds **conversation summarization** — the ability to compress long conversations into concise summaries that capture the essential information without requiring you to read through every message.

---

## Goals and Success Criteria

### Primary Goals

1. **Semantic search** — Find memories by meaning, not just keywords, using vector embeddings.
2. **Memory categories** — Organize memories into categories with different access rules and encryption keys.
3. **Conversation summarization** — Compress long conversations into concise, information-rich summaries.
4. **Memory consolidation** — Periodically merge related records, extract key facts, and detect contradictions.
5. **Search ranking** — Return results ordered by relevance, with explanations of why each result matches.
6. **Memory statistics** — Track and report on the state of your knowledge base.

### Success Criteria

You know Phase 1 is complete when:

- You can search for a concept and get relevant results even when the exact words don't match
- Search results are ranked by relevance with clear explanations
- Long conversations can be summarized into key takeaways
- Related memories are automatically merged over time
- Contradictions in your knowledge base are detected and flagged
- Memory categories have appropriate access controls
- You can view statistics about your knowledge base (record counts, sizes, last updates)

---

## Architecture

### What Phase 1 Adds

Phase 1 builds on the foundation from Phase 0 by adding several new components:

```
Phase 0 Components:
├── CLI Interface
├── Memory Service (with remote storage)
├── Encryption Layer
├── Key Management
└── Local RAM Cache

Phase 1 Adds:
├── Embedding Service (vector generation)
├── Vector Index (remote encrypted)
├── Search Engine (hybrid search)
├── Summarization Service (conversation compression)
├── Consolidation Engine (memory maintenance)
├── Category Manager (access control)
└── Statistics Tracker (knowledge base metrics)
```

### Data Flow for Semantic Search

When you search for something:

```
Your query: "Docker networking configuration"
    ↓
Embedding Service converts query to vector
    ↓
Vector Index (remote encrypted) finds semantically similar vectors
    ↓
Keyword search finds exact matches (parallel)
    ↓
Search Engine combines and ranks results
    ↓
Results returned with relevance scores and explanations
```

### Data Flow for Consolidation

The consolidation process runs periodically:

```
Scheduler triggers consolidation job
    ↓
Consolidation Engine loads recent records
    ↓
Groups related records by topic
    ↓
For each group:
    ├── Merge related facts
    ├── Extract key information
    ├── Detect contradictions
    └── Create consolidated summary
    ↓
Original records archived (not deleted)
    ↓
Consolidated records stored
    ↓
Audit log updated
```

---

## Data Models

### Vector Embedding Record

Stores the vector representation of a memory record for semantic search.

**Fields:**

- `record_id` — Reference to the memory record (UUID, foreign key).
- `embedding` — The vector representation (array of floats, typically 384-768 dimensions depending on the model).
- `model_version` — Which embedding model generated this vector (for re-embedding when models change).
- `created_at` — When the embedding was generated.
- `remote_path` — The path/key in remote storage where the encrypted embedding is stored.

**Design Decisions:**

Storing embeddings separately from the memory records keeps the encrypted data clean and allows embeddings to be regenerated without re-encrypting the source data. The model version field ensures that if you switch embedding models, you can re-embed your entire knowledge base. Embeddings are stored remotely in encrypted form.

### Search Result Record

Represents a single result from a search operation.

**Fields:**

- `record_id` — The matching memory record.
- `relevance_score` — How relevant this result is (0.0 to 1.0).
- `match_type` — How this result was found: semantic (meaning-based), keyword (exact match), or hybrid (both).
- `explanation` — Human-readable explanation of why this result matches.
- `snippet` — The relevant portion of the content (decrypted).

### Conversation Summary Record

Stores a compressed summary of a conversation session.

**Fields:**

- `session_id` — Reference to the original conversation.
- `encrypted_summary` — The summary content, encrypted.
- `key_topics` — List of main topics discussed (encrypted JSON).
- `action_items` — Any tasks or follow-ups mentioned (encrypted JSON).
- `original_length` — Number of messages in the original conversation.
- `compression_ratio` — How much the conversation was compressed.
- `created_at` — When the summary was generated.

### Consolidation Record

Tracks memory consolidation operations and their results.

**Fields:**

- `id` — Unique identifier.
- `operation` — Type of consolidation: merge, extract, contradict, summarize.
- `source_records` — List of record IDs that were consolidated.
- `result_record` — The new consolidated record ID.
- `changes` — Description of what changed.
- `created_at` — When the consolidation occurred.

### Memory Statistics Record

Caches knowledge base statistics for quick access.

**Fields:**

- `metric_name` — The statistic name (total_records, records_by_category, total_size, etc.).
- `metric_value` — The statistic value.
- `updated_at` — When the statistic was last calculated.

---

## API Design

### Search Endpoints

**Semantic search**

- Method: POST
- Path: /memory/search
- Request body: query (string), category (optional string), date_range (optional), limit (optional, default 10), min_score (optional, default 0.3)
- Response: list of search results with record_id, relevance_score, match_type, explanation, snippet
- Behavior: Converts query to embedding, finds similar vectors, combines with keyword search, ranks results, decrypts snippets for display.

**Hybrid search**

- Method: POST
- Path: /memory/search/hybrid
- Request body: query (string), semantic_weight (float, 0.0-1.0, default 0.7), keyword_weight (float, 0.0-1.0, default 0.3), category (optional), limit (optional)
- Response: list of search results with combined scores
- Behavior: Runs both semantic and keyword search in parallel, normalizes scores, combines with specified weights, returns ranked results.

**Search suggestions**

- Method: GET
- Path: /memory/search/suggest
- Query parameters: partial_query (string)
- Response: list of suggested queries based on your memory content
- Behavior: Autocomplete suggestions derived from your stored memories.

### Category Endpoints

**List categories**

- Method: GET
- Path: /memory/categories
- Response: list of categories with name, record_count, last_updated, size

**Get category details**

- Method: GET
- Path: /memory/categories/{category_name}
- Response: category name, description, record_count, access_level, created_at

**Create category**

- Method: POST
- Path: /memory/categories
- Request body: name (string), description (string), access_level (string)
- Response: category details
- Behavior: Creates a new category with its own encryption key.

### Summarization Endpoints

**Summarize a conversation**

- Method: POST
- Path: /memory/summarize/{session_id}
- Response: summary, key_topics, action_items, compression_ratio
- Behavior: Loads conversation, generates summary using LLM, stores summary, returns results.

**Get conversation summary**

- Method: GET
- Path: /memory/summarize/{session_id}
- Response: summary record if it exists, 404 otherwise

**List all summaries**

- Method: GET
- Path: /memory/summaries
- Query parameters: limit (optional), offset (optional)
- Response: list of summaries with session_id, key_topics, created_at

### Consolidation Endpoints

**Trigger consolidation**

- Method: POST
- Path: /memory/consolidate
- Request body: category (optional, defaults to all), force (boolean, defaults to false)
- Response: consolidation job ID, estimated completion time
- Behavior: Starts a consolidation job. If force is false, only consolidates records older than the threshold.

**Get consolidation status**

- Method: GET
- Path: /memory/consolidate/{job_id}
- Response: job status (pending, running, completed, failed), progress, results

**Get consolidation history**

- Method: GET
- Path: /memory/consolidate/history
- Query parameters: limit (optional)
- Response: list of past consolidation operations with their results

### Statistics Endpoints

**Get memory statistics**

- Method: GET
- Path: /memory/stats
- Response: total_records, records_by_category, total_size, oldest_record, newest_record, last_consolidation, search_count

---

## Implementation Details

### Step 1: Embedding Service

**Choose an embedding model**

For local embedding generation, the recommended model is `all-MiniLM-L6-v2` from the sentence-transformers library. It produces 384-dimensional vectors, is fast enough for real-time use, and provides good semantic understanding.

For higher quality at the cost of speed, consider `all-mpnet-base-v2` which produces 768-dimensional vectors.

For cloud-based embedding, OpenAI's `text-embedding-3-small` produces 1536-dimensional vectors with excellent quality.

**Embedding generation**

Implement a service that:
1. Takes plaintext content as input
2. Preprocesses the text (truncation, cleaning)
3. Generates a vector embedding using the chosen model
4. Returns the embedding vector

The service should handle:
- Text that exceeds the model's maximum token limit (truncation)
- Empty or very short text (return a zero vector or handle gracefully)
- Model loading and caching (load once, reuse)
- Batch embedding for efficiency

**Embedding storage**

When a memory record is stored or updated:
1. The Memory Service encrypts the content
2. The Embedding Service generates an embedding from the plaintext
3. The embedding is stored alongside the encrypted record (not encrypted, as embeddings don't contain recoverable personal information)
4. The vector is indexed for fast similarity search

### Step 2: Vector Index

**Local vector index (FAISS)**

For Phase 1, use Facebook AI Similarity Search (FAISS) as the local vector index. FAISS provides:
- Fast approximate nearest neighbor search
- Multiple index types (flat, IVF, HNSW)
- Memory-efficient storage
- GPU acceleration (optional)

**Index creation**

Build a FAISS index from all stored embeddings:
1. Download all embeddings from remote storage (encrypted)
2. Decrypt embeddings locally
3. Choose an index type (start with FlatL2 for accuracy, move to HNSW for speed)
4. Create the index with the appropriate dimensionality
5. Add all vectors to the index
6. Maintain a mapping from index position to record ID

**Index updates**

When new records are added or existing records are modified:
1. Generate the new embedding
2. Add it to the FAISS index
3. Update the position-to-record-ID mapping
4. Upload the updated index to remote storage (encrypted)

**Index persistence**

Save the FAISS index to remote storage:
- Encrypt the index before upload
- Load on startup (download from remote)
- Version the index to handle schema changes

### Step 3: Search Engine

**Hybrid search implementation**

The Search Engine combines semantic and keyword search:

1. **Semantic search:**
   - Convert query to embedding
   - Search FAISS for top-K similar vectors
   - Retrieve corresponding records
   - Calculate semantic relevance scores

2. **Keyword search:**
   - Tokenize query into keywords
   - Search an inverted index or use SQL LIKE queries
   - Retrieve matching records
   - Calculate keyword relevance scores

3. **Score combination:**
   - Normalize both score types to 0.0-1.0 range
   - Combine with configurable weights (semantic_weight + keyword_weight = 1.0)
   - Rank by combined score

**Relevance scoring**

For semantic search, relevance is based on cosine similarity between the query embedding and stored embeddings. Higher similarity means higher relevance.

For keyword search, relevance is based on term frequency, inverse document frequency, and match position.

**Explanation generation**

For each search result, generate a human-readable explanation:
- For semantic matches: "This record discusses concepts similar to your query about [topic]"
- For keyword matches: "This record contains the keywords [keyword1, keyword2]"
- For hybrid matches: "This record matches both by meaning and by specific terms"

**Snippet extraction**

Extract the most relevant portion of each result for display:
1. Find the sentence or paragraph that best matches the query
2. Highlight matching terms or concepts
3. Return a concise snippet (100-200 characters)

### Step 4: Category Manager

**Category definition**

Define default categories:
- **personal** — Biographical information, preferences, habits, physical description
- **projects** — Project details, goals, status, technical decisions
- **relationships** — People you know, context about them, interactions
- **technical** — Tools, configurations, solutions, code snippets
- **research** — Papers, articles, findings, analysis
- **ideas** — Brainstorming, future plans, concepts

**Category access rules**

Each category has access rules that control when the AI can read or write:

- **personal** — Read: always. Write: with confirmation.
- **projects** — Read: always. Write: always.
- **relationships** — Read: limited (don't dump entire relationship DB in context). Write: with confirmation.
- **technical** — Read: always. Write: always.
- **research** — Read: always. Write: always.
- **ideas** — Read: always. Write: always.

**Category encryption keys**

Each category has its own encryption key, derived from the master key:
- Master key encrypts category keys
- Category keys encrypt records in that category
- Compromising one category doesn't affect others

### Step 5: Conversation Summarization

**Summarization approach**

When summarizing a conversation:
1. Load all messages in the conversation
2. Prepare a prompt for the LLM that asks for a concise summary
3. Include instructions to extract key topics, decisions, and action items
4. Send to the LLM for generation
5. Parse the response into structured fields
6. Store the summary record

**Summary prompt structure**

The summarization prompt should ask for:
- A 2-3 sentence summary of the conversation
- A list of key topics discussed (3-5 items)
- Any action items or follow-ups mentioned
- Any decisions or conclusions reached
- Any technical details worth preserving

**Progressive summarization**

For very long conversations, use progressive summarization:
1. Divide conversation into chunks (e.g., every 20 messages)
2. Summarize each chunk
3. Combine chunk summaries into a final summary
4. This prevents exceeding the LLM's context window

**Summary updates**

When new messages are added to a conversation:
- If a summary exists, update it rather than regenerating from scratch
- Merge new information with existing summary
- Update key topics and action items
- Track the compression ratio

### Step 6: Consolidation Engine

**Consolidation triggers**

Consolidation runs:
- Automatically on a schedule (e.g., weekly)
- Manually when requested via API
- After reaching a threshold of new records (e.g., 100 new records)

**Merge operation**

When multiple records discuss the same topic:
1. Identify records with high semantic similarity (above threshold)
2. Group them by topic
3. For each group, generate a consolidated record that:
   - Combines all unique facts
   - Removes redundancy
   - Preserves important details
   - Notes any contradictions
4. Archive original records (mark as consolidated, keep for reference)
5. Store the consolidated record

**Extract operation**

Extract key facts from records:
1. Identify records with extractable information (dates, names, configurations, decisions)
2. Generate structured fact records
3. Link extracted facts to source records
4. Store as separate, easily searchable records

**Contradiction detection**

Identify conflicting information:
1. Compare records that discuss the same topic
2. Look for factual contradictions (e.g., "I use Python 3.10" vs "I use Python 3.11")
3. Flag contradictions for user review
4. Suggest resolution (which fact is more recent, which is more likely correct)

**Consolidation prompt**

Use an LLM to assist consolidation:
- Provide the group of related records
- Ask for: merged summary, extracted facts, contradictions, confidence level
- Parse the structured response
- Store results

### Step 7: Statistics Tracker

**Tracked metrics**

- Total record count
- Records by category
- Total storage size (encrypted data)
- Average record size
- Oldest record timestamp
- Newest record timestamp
- Last consolidation timestamp
- Search count (total and by day)
- Most searched topics
- Conversation count
- Average conversation length
- Total tokens processed

**Statistics updates**

Update statistics:
- On every store/delete operation (incremental updates)
- On consolidation (full recalculation)
- On demand (when requested via API)

**Statistics caching**

Cache statistics to avoid recalculating on every request:
- Store in a dedicated database table
- Update incrementally when possible
- Full recalculation on startup or consolidation

---

## Dependencies

### New Dependencies for Phase 1

- **sentence-transformers** — Local embedding model
- **faiss-cpu** or **faiss-gpu** — Vector similarity search
- **numpy** — Numerical operations for embeddings
- **scikit-learn** — For score normalization and clustering

### Existing Dependencies Used

- **boto3** — Remote storage operations (from Phase 0)
- **cryptography** — Encrypting embeddings before upload

---

## Testing

### Unit Tests

**Embedding tests**
- Test that embeddings are generated with correct dimensions
- Test that similar content produces similar embeddings
- Test that different content produces different embeddings
- Test batch embedding efficiency

**Search tests**
- Test semantic search finds relevant results
- Test keyword search finds exact matches
- Test hybrid search combines both effectively
- Test search with filters (category, date range)
- Test relevance score calculation
- Test explanation generation

**Summarization tests**
- Test that summaries capture key information
- Test that summaries are shorter than original conversations
- Test progressive summarization for long conversations
- Test summary updates when new messages arrive

**Consolidation tests**
- Test that related records are correctly identified
- Test that merged records contain all unique facts
- Test contradiction detection
- Test that original records are preserved

### Integration Tests

**End-to-end memory flow**
- Store a record → generate embedding → index in FAISS → search → retrieve
- Start a conversation → add messages → summarize → retrieve summary
- Store related records → run consolidation → verify merged result

**Search accuracy tests**
- Create a test set of records with known topics
- Run searches with various queries
- Verify that relevant results are returned
- Measure precision and recall

### Manual Testing

After Phase 1 is complete:
- Store memories about several different topics
- Search for each topic using different phrasings
- Verify that semantic search works (finds related content without exact keyword matches)
- Verify that search results are encrypted in remote storage
- Have a long conversation and summarize it
- Run consolidation and check that related memories are merged
- View statistics to confirm everything is tracked

---

## Edge Cases

### Embedding Model Changes

If you change the embedding model:
- All existing embeddings need to be regenerated
- Provide a migration command that re-embeds all records
- Track which model version generated each embedding
- Search should still work during migration (fall back to keyword search for un-embedded records)

### Empty or Short Content

If a memory record has very short content:
- Generate an embedding anyway (it will be less meaningful)
- Search results for short records may be less accurate
- Consider warning the user if content is too short to be useful

### Search Result Overflow

If a search returns too many results:
- Limit to the top N results by default
- Allow the user to request more results
- Paginate results for large result sets

### Consolidation Conflicts

If consolidation produces a record that conflicts with user expectations:
- Always archive original records (never delete)
- Provide a way to view what changed
- Allow the user to revert consolidation if needed

### Large Knowledge Base

As the knowledge base grows:
- FAISS index may become large (optimize index type)
- Search speed may degrade (use HNSW or IVF indexes)
- Consolidation may take longer (run in background)
- Consider using a vector database (pgvector) instead of FAISS for very large datasets

### Remote Storage Latency

If remote storage is slow:
- Use the local cache for recent embeddings
- Consider prefetching embeddings for likely queries
- Show loading indicators for remote operations
- Log slow operations for monitoring

---

## Deliverables

When Phase 1 is complete, you will have:

1. **Semantic search capability** — Find memories by meaning, not just keywords.

2. **Hybrid search engine** — Combines semantic and keyword search for best results.

3. **Search result ranking** — Results ordered by relevance with explanations.

4. **Memory categories** — Organized storage with different access rules per category.

5. **Conversation summarization** — Compress long conversations into key takeaways.

6. **Memory consolidation** — Background process that merges related records and detects contradictions.

7. **Knowledge base statistics** — Track the state and usage of your memory system.

8. **Remote vector index** — FAISS-based index for fast similarity search, stored remotely in encrypted form.

9. **Embedding service** — Local embedding generation using sentence-transformers.

10. **Updated test suite** — Comprehensive tests for all new functionality.

---

## What Comes Next

After Phase 1, you will move to **Phase 2: Research Agent**, which adds:
- Continuous web research from multiple sources
- Relevance scoring for external information
- Daily briefing generation
- Research database with deduplication

Phase 1's semantic search capabilities will be directly useful for Phase 2's relevance engine — the same embedding and search infrastructure can score how relevant a research item is to your interests.

---

*Phase 1 transforms MYSTI's remote storage into an intelligent memory system that understands meaning.*
