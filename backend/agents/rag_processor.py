import os
from typing import List, Dict
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

class RAGProcessor:
    def __init__(self, data_dir: str = "data/", index_name: str = "tracetrust_index"):
        self.data_dir = data_dir
        self.index_path = os.path.join(data_dir, index_name)
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vector_store = None

    def ingest_report(self, pdf_path: str):
        """
        Chunk a PDF report and add it to the FAISS index.
        """
        print(f"Ingesting report: {pdf_path}")
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", ".", "!", "?", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)
        
        if self.vector_store is None:
            self.vector_store = FAISS.from_documents(chunks, self.embeddings)
        else:
            self.vector_store.add_documents(chunks)
        
        # Save index locally
        self.vector_store.save_local(self.index_path)
        print(f"Index updated and saved to {self.index_path}")

    def query_report(self, query: str, k: int = 5) -> List[Dict]:
        """
        Query the FAISS index for relevant chunks.
        """
        if self.vector_store is None:
            if os.path.exists(self.index_path):
                self.vector_store = FAISS.load_local(self.index_path, self.embeddings, allow_dangerous_deserialization=True)
            else:
                return []

        results = self.vector_store.similarity_search_with_score(query, k=k)
        return [{"content": res[0].page_content, "metadata": res[0].metadata, "score": float(res[1])} for res in results]

if __name__ == "__main__":
    # Test stub
    processor = RAGProcessor()
    # processor.ingest_report("data/amazon_2024_sustainability_report.pdf")
    # print(processor.query_report("List all manufacturing facilities"))
