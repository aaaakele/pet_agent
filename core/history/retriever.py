"""Vector search for similar historical messages using ChromaDB built-in embeddings."""

import asyncio
from typing import Dict, List

from config.settings import settings
from utils.logger import logger


class HistoryRetriever:
    """Thin wrapper around ChromaDB with built-in ONNX embedding. No heavy deps."""

    def __init__(self):
        self._client = None
        self._collection = None
        self._embed_fn = None
        self._available = False
        self._init_attempted = False

    def _ensure_client(self) -> bool:
        if self._init_attempted:
            return self._available
        self._init_attempted = True

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self._client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
            self._embed_fn = embedding_functions.DefaultEmbeddingFunction()
            self._collection = self._client.get_or_create_collection(
                name="chat_history",
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embed_fn,
            )
            self._available = True
            logger.info("ChromaDB + ONNX embedding ready")
            return True
        except Exception as e:
            logger.warning(f"ChromaDB unavailable, RAG disabled: {e}")
            self._available = False
            return False

    async def add_messages(self, messages: List[Dict]) -> None:
        if not messages or not self._ensure_client():
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._add_sync, messages)

    def _add_sync(self, messages: List[Dict]) -> None:
        if not self._available:
            return
        ids = [str(m["id"]) for m in messages]
        texts = [m["content"] for m in messages]
        metadatas = [
            {"role": m["role"], "timestamp": m["timestamp"]}
            for m in messages
        ]
        try:
            self._collection.add(
                ids=ids, metadatas=metadatas, documents=texts,
            )
        except Exception as e:
            logger.error(f"ChromaDB add failed: {e}")

    async def search_similar(
        self, query: str, k: int = 3, role: str = None
    ) -> List[str]:
        if not self._ensure_client():
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._search_sync, query, k, role)

    def _search_sync(self, query: str, k: int, role: str) -> List[str]:
        where = {"role": role} if role else None
        try:
            results = self._collection.query(
                query_texts=[query], n_results=k, where=where,
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []
        documents = results.get("documents", [[]])[0]
        return documents if documents else []

    async def index_unembedded(self, store) -> int:
        """Index all unembedded messages from MessageStore. Returns count indexed."""
        messages = store.get_unembedded_messages(limit=100)
        if not messages:
            return 0

        batch = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "timestamp": m.created_at,
            }
            for m in messages
        ]
        await self.add_messages(batch)
        store.mark_embedded([m.id for m in messages])
        return len(batch)
