"""
RAG Processor — FAISS Vector Search for PDF Reports

Ported from harshith branch and adapted for async pipeline integration.
Uses LangChain + FAISS + HuggingFace embeddings (all-MiniLM-L6-v2)
to semantically search relevant sections of sustainability reports.
"""

import asyncio
import os
from typing import List, Dict, Optional

_FAISS_AVAILABLE = False
_RAG_IMPORT_ERROR = None

try:
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    _FAISS_AVAILABLE = True
except ImportError as e:
    _RAG_IMPORT_ERROR = str(e)


class RAGProcessor:
    """Semantic search over PDF reports using FAISS vector index."""

    def __init__(self, data_dir: str = "data/", index_name: str = "tracetrust_index"):
        self.data_dir = data_dir
        self.index_path = os.path.join(data_dir, index_name)
        self.vector_store = None
        self._embeddings = None
        self._available = _FAISS_AVAILABLE

    @property
    def available(self) -> bool:
        return self._available

    @property
    def import_error(self) -> Optional[str]:
        return _RAG_IMPORT_ERROR

    def _get_embeddings(self):
        """Lazy-load the embedding model (takes ~2s on first call)."""
        if self._embeddings is None and self._available:
            self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        return self._embeddings

    async def ingest_report(self, pdf_path: str) -> int:
        """Chunk a PDF and build a FAISS index. Returns chunk count."""
        if not self._available:
            return 0

        loop = asyncio.get_event_loop()

        def _ingest():
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
                separators=["\n\n", "\n", ".", "!", "?", " ", ""],
            )
            chunks = splitter.split_documents(documents)

            embeddings = self._get_embeddings()
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(chunks, embeddings)
            else:
                self.vector_store.add_documents(chunks)

            # Persist to disk
            os.makedirs(self.data_dir, exist_ok=True)
            self.vector_store.save_local(self.index_path)
            return len(chunks)

        try:
            count = await asyncio.wait_for(
                loop.run_in_executor(None, _ingest),
                timeout=60.0,  # 60s timeout for large PDFs
            )
            return count
        except (asyncio.TimeoutError, Exception) as e:
            print(f"RAG ingest error: {e}")
            return 0

    async def query_report(self, query: str, k: int = 10) -> List[Dict]:
        """Query the FAISS index for the k most relevant chunks."""
        if not self._available:
            return []

        loop = asyncio.get_event_loop()

        def _query():
            # Load from disk if not in memory
            if self.vector_store is None:
                if os.path.exists(self.index_path):
                    embeddings = self._get_embeddings()
                    self.vector_store = FAISS.load_local(
                        self.index_path, embeddings,
                        allow_dangerous_deserialization=True,
                    )
                else:
                    return []

            results = self.vector_store.similarity_search_with_score(query, k=k)
            return [
                {
                    "content": res[0].page_content,
                    "metadata": res[0].metadata,
                    "score": float(res[1]),
                }
                for res in results
            ]

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _query),
                timeout=15.0,
            )
        except (asyncio.TimeoutError, Exception) as e:
            print(f"RAG query error: {e}")
            return []
