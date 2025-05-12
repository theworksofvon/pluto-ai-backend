"""
Retrieve documents related to query
"""

from typing import Any, Optional
from llama_parse import LlamaParse
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import VectorStoreIndex, Document
from typing import List
from llama_index.core.storage import StorageContext
from config import config
from llama_index.llms.ollama import Ollama
from llama_index.core.settings import Settings
import asyncio


class BaseRetriever:
    """Retriever class to create vector stores and use with models in order to answer questions better"""

    def __init__(
        self,
        parser: Optional[LlamaParse] = None,
        embed_model: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> None:
        self.parser = parser or LlamaParse(
            result_type="markdown", api_key=config.LLAMA_CLOUD_API_KEY
        )
        self.embed_model = embed_model or HuggingFaceEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.llm = llm or Ollama(
            model=config.OLLAMA_MODEL_NAME, base_url=config.OLLAMA_API_URL
        )

        # Configure global settings
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        Settings.chunk_size = 1024
        Settings.chunk_overlap = 20

        self.vector_index = None
        self.query_engine = None

    def create_vector_store(self, documents, persist_dir: Optional[str] = None):
        """Creates vector store with persisted data if specified"""
        if persist_dir:
            storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
            self.vector_index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
            )
        else:
            self.vector_index = VectorStoreIndex.from_documents(
                documents,
            )

        self.query_engine = self.vector_index.as_query_engine()
        return self.vector_index

    async def parse_documents(
        self, file_paths: List[str], doc_type: str
    ) -> List[Document]:
        """
        Parse documents from file paths using LlamaParse
        """
        accepted_doc_types = [".pdf"]

        if doc_type not in accepted_doc_types:
            raise ValueError("The only accepted documents are .pdf")

        documents = []
        for file_path in file_paths:
            # Use the async version of load_data
            parsed_docs = await self.parser.aload_data(file_path)
            documents.extend(parsed_docs)
        return documents

    def query(self, query_text: str) -> dict:
        """
        Query the vector store for relevant documents

        Args:
            query_text (str): The query text to search for

        Returns:
            Dict: Query response containing relevant documents and their similarity scores
        """
        if self.vector_index is None:
            raise ValueError(
                "Vector store has not been created yet. Call create_vector_store first."
            )

        if self.query_engine is None:
            self.query_engine = self.vector_index.as_query_engine()

        response = self.query_engine.query(query_text)
        return {"response": str(response)}
