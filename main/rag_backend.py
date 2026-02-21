"""
RAG Backend — reusable classes with no module-level side effects.
Imported by app.py (Streamlit) and can also be used from scripts.
"""

import os
import uuid
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# PDF processing
# ---------------------------------------------------------------------------

def process_pdfs(pdf_paths: List[str]) -> List[Any]:
    """Load one or more PDF files and return LangChain Document objects."""
    all_documents = []
    for path in pdf_paths:
        p = Path(path)
        try:
            loader = PyPDFLoader(str(p))
            docs = loader.load()
            for doc in docs:
                doc.metadata["source_file"] = p.name
                doc.metadata["file_type"] = "pdf"
            all_documents.extend(docs)
        except Exception as e:
            print(f"Error loading {p.name}: {e}")
    return all_documents


def split_documents(documents: List[Any], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Any]:
    """Split documents into smaller chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_documents(documents)


# ---------------------------------------------------------------------------
# Embedding manager
# ---------------------------------------------------------------------------

class EmbeddingManager:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, show_progress_bar=False)


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------

class VectorStore:
    def __init__(
        self,
        collection_name: str = "pdf_documents",
        persist_directory: str = "../data/vector_store",
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "PDF document embeddings for RAG"},
        )

    def count(self) -> int:
        return self.collection.count()

    def add_documents(self, documents: List[Any], embeddings: np.ndarray):
        ids, metadatas, texts, emb_list = [], [], [], []
        for i, (doc, emb) in enumerate(zip(documents, embeddings)):
            ids.append(f"doc_{uuid.uuid4().hex[:8]}_{i}")
            meta = dict(doc.metadata)
            meta["doc_index"] = i
            meta["content_length"] = len(doc.page_content)
            metadatas.append(meta)
            texts.append(doc.page_content)
            emb_list.append(emb.tolist())
        self.collection.add(
            ids=ids,
            embeddings=emb_list,
            metadatas=metadatas,
            documents=texts,
        )

    def reset(self):
        """Delete all documents in the collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "PDF document embeddings for RAG"},
        )

    def query(self, query_embedding: List[float], top_k: int) -> Dict:
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class RAGRetriever:
    def __init__(self, vector_store: VectorStore, embedding_manager: EmbeddingManager):
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager

    def retrieve(
        self, query: str, top_k: int = 5, score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        query_emb = self.embedding_manager.embed([query])[0].tolist()
        results = self.vector_store.query(query_emb, top_k)
        retrieved = []
        if results["documents"] and results["documents"][0]:
            for i, (doc_id, document, metadata, distance) in enumerate(
                zip(
                    results["ids"][0],
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                similarity_score = 1 - (distance / 2)
                if similarity_score >= score_threshold:
                    retrieved.append(
                        {
                            "id": doc_id,
                            "content": document,
                            "metadata": metadata,
                            "similarity_score": similarity_score,
                            "distance": distance,
                            "rank": i + 1,
                        }
                    )
        return retrieved


# ---------------------------------------------------------------------------
# Cross-encoder reranker
# ---------------------------------------------------------------------------

class CrossEncoderReranker:
    """Reranks retrieved chunks using a cross-encoder for higher precision."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, docs: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        if not docs:
            return docs
        pairs = [(query, doc["content"]) for doc in docs]
        scores = self.model.predict(pairs)
        for doc, score in zip(docs, scores):
            doc["rerank_score"] = float(score)
        reranked = sorted(docs, key=lambda d: d["rerank_score"], reverse=True)[:top_n]
        for i, doc in enumerate(reranked):
            doc["rank"] = i + 1
            # Normalise cross-encoder score to 0-1 for display (sigmoid)
            doc["similarity_score"] = float(1 / (1 + np.exp(-doc["rerank_score"] / 3)))
        return reranked


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

_SUMMARY_PATTERNS = [
    "summarize", "summarise", "summary", "overview", "what is this",
    "what is the document", "what is this document", "what is this pdf",
    "what does this document", "what does this pdf", "tell me about",
    "about the document", "about the pdf", "about this file",
    "what are the main", "key points", "key topics", "main topics",
    "describe the document", "describe the pdf",
]

def _is_summary_query(query: str) -> bool:
    q = query.lower().strip()
    return any(p in q for p in _SUMMARY_PATTERNS)

def build_llm(model_name: str = None, temperature: float = 0.7) -> ChatGroq:
    model_name = model_name or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    return ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name=model_name,
        temperature=temperature,
        max_tokens=2048,
    )


def expand_query(query: str, llm: ChatGroq) -> str:
    """Rewrite query to improve retrieval recall."""
    prompt = (
        "Rewrite the following question to be more specific and detailed "
        "so it can better match relevant text in a document. "
        "Return ONLY the rewritten question, nothing else.\n\n"
        f"Original question: {query}\n\nRewritten question:"
    )
    try:
        response = llm.invoke(prompt)
        expanded = response.content.strip()
        # Combine original + expanded for broader coverage
        return f"{query} {expanded}"
    except Exception:
        return query


def rag_enhanced(
    query: str,
    retriever: RAGRetriever,
    llm: ChatGroq,
    top_k: int = 5,
    min_score: float = 0.2,
    reranker: "CrossEncoderReranker | None" = None,
) -> Dict[str, Any]:
    is_summary = _is_summary_query(query)

    # Step 1: expand query for better recall (skip for summaries)
    retrieval_query = query if is_summary else expand_query(query, llm)

    # Step 2: retrieve — fetch more candidates when reranking
    fetch_k = top_k * 3 if reranker else top_k
    threshold = 0.0 if is_summary else min_score
    results = retriever.retrieve(retrieval_query, top_k=fetch_k, score_threshold=threshold)

    if not results:
        return {
            "answer": "No documents are indexed yet. Please upload a PDF from the sidebar first.",
            "sources": [],
            "confidence": 0.0,
            "context": "",
        }

    # Step 3: rerank
    if reranker and not is_summary:
        results = reranker.rerank(query, results, top_n=top_k)
    else:
        results = results[:top_k]

    context = "\n\n".join(
        f"Document {doc['rank']} (Score: {doc['similarity_score']:.2f}):\n{doc['content']}"
        for doc in results
    )
    sources = [
        {
            "source": doc["metadata"].get("source_file", "unknown"),
            "page": doc["metadata"].get("page", "unknown"),
            "score": doc["similarity_score"],
            "preview": (
                doc["content"][:200] + "..."
                if len(doc["content"]) > 200
                else doc["content"]
            ),
        }
        for doc in results
    ]
    confidence = max(doc["similarity_score"] for doc in results)

    if is_summary:
        prompt = (
            "You are a helpful assistant. Based on the document excerpts below, "
            "provide a clear and concise summary of what the document is about.\n"
            "Cover the main topics, purpose, and key points found in the text.\n"
            "Use ONLY information present in the excerpts below — do not add outside knowledge.\n\n"
            f"Document excerpts:\n{context}\n\n"
            "Summary:"
        )
    else:
        prompt = (
            "You are a helpful assistant. Use the context below to answer the question.\n"
            "- Use ONLY information present in the context.\n"
            "- Do NOT use outside knowledge or make up facts.\n"
            "- If the context is genuinely unrelated to the question, say: "
            "'The uploaded documents do not appear to contain information about this topic.'\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )
    response = llm.invoke(prompt)
    return {
        "answer": response.content.strip(),
        "sources": sources,
        "confidence": confidence,
        "context": context,
    }
