import faiss

index = faiss.read_index('/Users/vbamba/Projects/collectedworks/indexes/faiss_index.bin')
print(f"Total embeddings in FAISS index: {index.ntotal}")
