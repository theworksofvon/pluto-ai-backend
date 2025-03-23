import os
from agency.retrievers import BaseRetriever


class RaptorRetriever(BaseRetriever):
    """RAPTOR NBA score report retriever"""

    def __init__(self, path: str) -> None:
        super().__init__(parser=None, embed_model=None)
        self.personality_docs = self.parse_documents(file_paths=[path], doc_type=".pdf")
        self.vector_index = self.create_vector_store(self.personality_docs)


base_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(base_dir)))
agency_dir = os.path.join(parent_dir, "agency")
shared_dir = os.path.join(agency_dir, "shared")
raptor_path = os.path.join(shared_dir, "raptor.pdf")
personality_retriever = RaptorRetriever(path=raptor_path)
