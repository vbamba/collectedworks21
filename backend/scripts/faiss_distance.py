import faiss
import numpy as np
import json

# Load FAISS index
index = faiss.read_index('/Users/vbamba/Projects/collectedworks/indexes/faiss_index.bin')

# Perform a full scan to collect distances
query_embedding = np.random.random((1, index.d)).astype('float32')
distances, indices = index.search(query_embedding, index.ntotal)

# Analyze distances
print(f"Min distance: {distances.min()}")
print(f"Max distance: {distances.max()}")
print(f"Mean distance: {distances.mean()}")
