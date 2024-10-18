import faiss
import numpy as np
import json
from sentence_transformers import SentenceTransformer

# Load FAISS index
index = faiss.read_index('/Users/vbamba/Projects/collectedworks/indexes/faiss_index.bin')

# Load metadata
with open('/Users/vbamba/Projects/collectedworks/indexes/metadata.json', 'r', encoding='utf-8') as f:
    metadata = json.load(f)

# Load model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Exact phrase query
query = "All can be done if the god-touch is there."
query_embedding = model.encode(query, convert_to_numpy=True).astype('float32')
query_embedding = np.expand_dims(query_embedding, axis=0)

# Perform search
distances, indices = index.search(query_embedding, 5)
print("Search Results:")
for distance, idx in zip(distances[0], indices[0]):
    if idx < len(metadata):
        snippet = metadata[idx]['snippet']
        print(f"Distance: {distance}, Snippet: {snippet}")
    else:
        print(f"Distance: {distance}, Snippet: Invalid Index {idx}")
