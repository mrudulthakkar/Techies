import os
from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path

def process_all_pdfs(pdf_directory):
    """Process all pdf files in a directory"""
    all_documents=[]
    pdf_dir= Path(pdf_directory)

    pdf_files= list(pdf_dir.glob("**/*.pdf"))
    print(f"Found {len(pdf_files)} PDF files to process")
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file.name}")
        try:
            loader= PyPDFLoader(str(pdf_file))
            documents= loader.load()

            for doc in documents:
                doc.metadata['source_file']= pdf_file.name
                doc.metadata['file_type']='pdf'
            all_documents.extend(documents)
            print(f"Loaded  {len(documents)} pages")
        except Exception as e:
            print(f" Error: {e}")
        
    print(f"\nTotal documents loaded: {len(documents)}")
    return all_documents

all_pdf_documents= process_all_pdfs("../data")

def split_documents(documemts, chunk_size=1000, chunk_overlap=200):
    """ Split documents into smaller chunks for better RAG performance"""
    text_splitter= RecursiveCharacterTextSplitter(
        chunk_size= chunk_size,
        chunk_overlap= chunk_overlap,
        length_function= len,
        separators=["\n\n", "\n", " ", ""]
    )
    split_docs= text_splitter.split_documents(documemts)
    print(f"Split {len(documemts)} documents into {len(split_docs)} chunks.")

    if split_docs:
        print(f"\nExample chunk:")
        print(f"content: {split_docs[0].page_content[:200]}...")
        print(f"Metadata: {split_docs[0].metadata}")

    return split_docs

chunks= split_documents(all_pdf_documents)

import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import uuid
from typing import List, Dict, Any, Tuple
from sklearn.metrics.pairwise import cosine_similarity

class EmbeddingManager:
    def __init__(self, model_name: str= "all-MiniLM-L6-v2"):
        self.model_name= model_name
        self.model= None
        self._load_model()
    
    def _load_model(self):
        try:
            print(f"Loading enbedding model: {self.model_name}")
            self.model= SentenceTransformer(self.model_name)
            print(f"Model loaded successfully. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            print(f"Error loading model {self.model_name}: {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        if not self.model:
            raise ValueError("Model not loaded")
        
        print(f"Generating embeddings for {len(texts)} texts...")
        embeddings= self.model.encode(texts, show_progress_bar=True)
        print(f"Generated  embeddings with shape: {embeddings.shape}")
        return embeddings
    
    
embedding_manager= EmbeddingManager()

class VectorStore:
    def __init__(self, collection_name: str= "pdf_documents", persist_directory: str= "../data/vector_store"):
        self.collection_name= collection_name
        self.persist_directory= persist_directory
        self.client= None
        self.collection= None
        self._initialize_store()

    def _initialize_store(self):
        try:
            os.makedirs(self.persist_directory, exist_ok=True)
            self.client= chromadb.PersistentClient(path= self.persist_directory)

            self.collection= self.client.get_or_create_collection(
                name= self.collection_name,
                metadata= {"description": "PDF document embeddings for RAG"}
            )
            print(f"Vectore store intialized. Collection: {self.collection_name}")
            print(f"Existing documents in collection : {self.collection.count()}")
        except Exception as e:
            print(f" Error  intializing vector store: {e}")
            raise

    def add_documents(self, documents: List[Any], embeddings: np.ndarray):
           if len(documents) != len(embeddings):
               raise ValueError("Number of documents must match number of embeddings")
           print(f"Adding {len(documents)} documents to vector store...")
           
           # Prepare data for ChromaDB
           ids = []
           metadatas = []
           documents_text = []
           embeddings_list = []
           
           for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
               # Generate unique ID,
               doc_id = f"doc_{uuid.uuid4().hex[:8]}_{i}"
               ids.append(doc_id)
               
               # Prepare metadata,
               metadata = dict(doc.metadata)
               metadata['doc_index'] = i
               metadata['content_length'] = len(doc.page_content)
               metadatas.append(metadata)
               
               # Document content,
               documents_text.append(doc.page_content)
               
               # Embedding,
               embeddings_list.append(embedding.tolist())
           
           # Add to collection,
           try:
               self.collection.add(
                   ids=ids,
                   embeddings=embeddings_list,
                   metadatas=metadatas,
                   documents=documents_text
               ),
               print(f"Successfully added {len(documents)} documents to vector store")
               print(f"Total documents in collection: {self.collection.count()}")
               
           except Exception as e:
               print(f"Error adding documents to vector store: {e}")
               raise
   
vector_store=VectorStore()

texts= [doc.page_content for doc in chunks]
embeddings= embedding_manager.generate_embeddings(texts)

vector_store.add_documents(chunks, embeddings)


class RAGRetriever:
    def __init__(self, vector_store: VectorStore, embedding_manager: EmbeddingManager):
        self.vector_store= vector_store
        self.embedding_manager= embedding_manager
    
    def retrieve(self, query: str, top_k: int =5, score_threshold: float=0.0)->List[Dict[str, Any]]:
        print(f"Retriving document for query: '{query}")
        print(f"Top K: {top_k}, Score threshold: {score_threshold}")

        query_embedding= self.embedding_manager.generate_embeddings([query])[0]

        try:
            results= self.vector_store.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k
            )
            retrieved_docs= []

            if results['documents'] and results['documents'][0]:
                documents= results['documents'][0]
                metadatas= results['metadatas'][0]
                distances= results['distances'][0]
                ids= results['ids'][0]

                for i, (doc_id, document, metadata, distance) in enumerate(zip(ids, documents, metadatas, distances)):
                    similarity_score = 1 - distance
                    if similarity_score >= score_threshold:
                        retrieved_docs.append({
                            'id': doc_id,
                            'content': document,
                            'metadata': metadata,
                            'similarity_score': similarity_score,
                            'distance': distance,
                            'rank': i + 1
                        })
            
                print(f"Retrieved {len(retrieved_docs)} documents (after filtering)")
            else:
                print("No documents found")
            
            return retrieved_docs
            
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []
        
rag_retriever=RAGRetriever(vector_store,embedding_manager)

rag_retriever.retrieve("what is the name of the hackthon?")
