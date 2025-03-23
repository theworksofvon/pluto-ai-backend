import os
from agency.retrievers import BaseRetriever


class PersonalityRetriever(BaseRetriever):
    """Pluto's personality retriever so respones can always align to this original personality"""

    def __init__(self, personality_docs_path: str) -> None:
        super().__init__(parser=None, embed_model=None)
        self.personality_docs = self.parse_documents(
            file_paths=[personality_docs_path], doc_type=".pdf"
        )
        self.vector_index = self.create_vector_store(self.personality_docs)


base_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(base_dir)))
agency_dir = os.path.join(parent_dir, "agency")
shared_dir = os.path.join(agency_dir, "shared")
personality_path = os.path.join(shared_dir, "personality.pdf")
personality_retriever = PersonalityRetriever(personality_docs_path=personality_path)
