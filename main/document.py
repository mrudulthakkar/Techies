from langchain_core.documents import Document
import os
from langchain_community.document_loaders import TextLoader
os.makedirs("../data/text_files", exist_ok=True)  
sample_texts= {
    "../data/text_files/python_intro.txt":"""
Retrieval-Augmented Generation (RAG) is a technique that enhances the accuracy and reliability of generative AI models by fetching facts from external sources. 
When a user asks a question, a RAG system first searches a database or document store for relevant information. 
It then retrieves those specific snippets of text and feeds them to the Large Language Model (LLM) along with the original prompt. 
By providing the LLM with this retrieved context, the model can generate answers that are grounded in your specific data, significantly reducing hallucinations and allowing the AI to answer questions about private or up-to-date information it wasn't originally trained on.
"""
}

for filepath, content in sample_texts.items():
    with open(filepath, 'w', encoding="utf-8") as f:
        f.write(content)

# print("file created")

loader= TextLoader("../data/text_files/python_intro.txt", encoding="utf-8")
document= loader.load()
# print(document)

from langchain_community.document_loaders import DirectoryLoader
dir_loader= DirectoryLoader(
    "../data/text_files",
    glob="**/*.txt",
    loader_cls= TextLoader,
    loader_kwargs={'encoding':'utf-8'},
    show_progress=False
)

documents= dir_loader.load()

from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader

dir_loader= DirectoryLoader(
    "../data/pdf",
    glob="**/*.pdf",
    loader_cls= PyMuPDFLoader,
    show_progress=False
)

pdf_documents= dir_loader.load()