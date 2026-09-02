"""Application context: wires settings, storage, keys, cache, audit and services."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from mysti.core.llm import LLMClient, create_llm_client
from mysti.exceptions import MystiError
from mysti.memory.cache import BlobCache
from mysti.memory.categories import CategoryManager
from mysti.memory.conversations import ConversationStore
from mysti.memory.embeddings import EmbeddingService
from mysti.memory.service import MemoryService
from mysti.memory.summarization import ConversationSummarizer
from mysti.research.briefing import DailyBriefing
from mysti.research.collector import ResearchCollector
from mysti.research.connectors import SourceConnector, build_connectors
from mysti.research.deep import DeepResearch
from mysti.research.relevance import RelevanceEngine
from mysti.research.scheduler import ResearchScheduler, SchedulerConfig
from mysti.research.sources import ResearchSourceConfig
from mysti.research.store import ResearchItemStore
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.security.keystore import SecretStore, create_secret_store
from mysti.settings import Settings
from mysti.storage.base import StorageBackend
from mysti.storage.local import LocalStorageBackend
from mysti.storage.s3 import S3StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Fully wired application object graph."""

    settings: Settings
    storage: StorageBackend
    keys: KeyManager
    cache: BlobCache
    audit: AuditLog
    memory: MemoryService
    conversations: ConversationStore
    llm: LLMClient
    first_run: bool = False
    category_manager: CategoryManager | None = None
    summarizer: ConversationSummarizer | None = None
    research_sources: ResearchSourceConfig | None = None
    research_items: ResearchItemStore | None = None
    relevance: RelevanceEngine | None = None
    collectors: list[SourceConnector] = field(default_factory=list)
    research_collector: ResearchCollector | None = None
    briefing: DailyBriefing | None = None
    deep_research: DeepResearch | None = None
    scheduler: ResearchScheduler | None = None
    _research_loaded: bool = field(default=False, init=False, repr=False)

    async def ensure_research(self) -> None:
        """Lazily build the research subsystem (connectors are expensive).

        Connector construction creates ``httpx.AsyncClient`` instances, which
        is measurably slow on Windows; research is optional at runtime, so it
        is deferred until a research command or the scheduler actually needs it.
        """
        if self._research_loaded:
            return
        self._research_loaded = True
        if self.research_sources is None:
            self.research_sources = ResearchSourceConfig(self.keys, self.storage, self.audit)
        if self.research_items is None:
            self.research_items = ResearchItemStore(self.keys, self.storage, self.audit)
        if self.relevance is None:
            self.relevance = RelevanceEngine(
                profile_path=(
                    Path(self.settings.interests_path) if self.settings.interests_path else None
                )
            )
        if not self.collectors:
            source_config = await self.research_sources.load()
            self.collectors = build_connectors(source_config)
        if self.research_collector is None:
            self.research_collector = ResearchCollector(
                self.collectors, self.research_sources, self.research_items, self.audit
            )
        if self.briefing is None:
            self.briefing = DailyBriefing(
                self.collectors,
                self.relevance,
                self.keys,
                self.storage,
                self.audit,
                min_score=self.settings.briefing_min_relevance,
            )
        if self.deep_research is None:
            self.deep_research = DeepResearch(
                self.collectors, self.relevance, self.keys, self.storage, self.audit
            )

    async def close(self) -> None:
        """Release resources (HTTP connections, scheduler)."""
        if self.scheduler is not None:
            self.scheduler.stop()
        await self.llm.aclose()
        for connector in self.collectors:
            await connector.aclose()


async def build_context(
    settings: Settings | None = None,
    storage: StorageBackend | None = None,
    secret_store: SecretStore | None = None,
) -> AppContext:
    """Create and initialize the application context.

    Args:
        settings: Settings instance; loaded from the environment when None.
        storage: Storage backend override (used by tests).
        secret_store: Secret store override (used by tests).

    Raises:
        MystiError: On invalid configuration or failed initialization.
    """
    settings = settings or Settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if storage is None:
        if settings.storage_provider == "local":
            storage = LocalStorageBackend(Path(settings.data_dir) / "remote_storage")
        else:
            storage = S3StorageBackend(
                bucket=settings.storage_bucket,
                access_key=settings.storage_access_key,
                secret_key=settings.storage_secret_key,
                endpoint=settings.storage_endpoint,
                region=settings.storage_region,
            )
    secret_store = secret_store or create_secret_store(settings)
    keys = KeyManager(secret_store, storage)
    first_run = await keys.ensure_initialized()
    cache = BlobCache(max_bytes=settings.cache_max_bytes, ttl_seconds=settings.cache_ttl)
    audit = AuditLog(Path(settings.data_dir) / "audit.jsonl")
    embeddings = EmbeddingService.from_settings(settings)
    memory = MemoryService(
        storage,
        keys,
        cache,
        audit,
        embeddings=embeddings,
        max_record_bytes=settings.max_record_bytes,
    )
    conversations = ConversationStore(storage, keys, audit)
    llm = create_llm_client(settings)
    summarizer = ConversationSummarizer(conversations, keys, storage, audit, llm=llm)
    category_manager = CategoryManager(memory, keys, storage, audit)
    relevance = RelevanceEngine(
        profile_path=Path(settings.interests_path) if settings.interests_path else None
    )
    research_sources = ResearchSourceConfig(keys, storage, audit)
    research_items = ResearchItemStore(keys, storage, audit)

    context = AppContext(
        settings=settings,
        storage=storage,
        keys=keys,
        cache=cache,
        audit=audit,
        memory=memory,
        conversations=conversations,
        llm=llm,
        first_run=first_run,
        category_manager=category_manager,
        summarizer=summarizer,
        research_sources=research_sources,
        research_items=research_items,
        relevance=relevance,
    )

    if settings.research_enabled:

        async def _run_collect() -> None:
            await context.ensure_research()
            assert context.research_collector is not None
            await context.research_collector.collect()

        async def _run_briefing() -> None:
            await context.ensure_research()
            assert context.briefing is not None
            await context.briefing.generate_briefing()

        async def _run_consolidate() -> None:
            from mysti.memory.consolidation import MemoryConsolidator

            consolidator = MemoryConsolidator(memory, audit, keys=keys, storage=storage)
            await consolidator.run()

        context.scheduler = ResearchScheduler(
            config=SchedulerConfig(
                briefing_hour=settings.research_briefing_hour,
                briefing_minute=settings.research_briefing_minute,
                collect_minutes=settings.research_collect_minutes,
                consolidate_day=settings.research_consolidation_day,
                consolidate_hour=settings.research_consolidation_hour,
                enabled=True,
            ),
            audit=audit,
            collect_cb=_run_collect,
            briefing_cb=_run_briefing,
            consolidate_cb=_run_consolidate,
        )

    audit.log(
        "system.start",
        "app",
        metadata={"provider": settings.storage_provider, "first_run": first_run},
    )
    return context


__all__ = ["AppContext", "MystiError", "build_context"]
