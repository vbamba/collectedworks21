import faiss
import numpy as np
import json
from sentence_transformers import SentenceTransformer

# Load model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Example snippet
snippet = "All can be done if the god-touch is there."

# Encode
snippet_embedding = model.encode(snippet, convert_to_numpy=True).astype('float32')
snippet_embedding = np.expand_dims(snippet_embedding, axis=0)

# Load FAISS index
index = faiss.read_index('/Users/vbamba/Projects/collectedworks21/backend/indexes/faiss_index.bin')

# Perform search
distances, indices = index.search(snippet_embedding, 1)
print("Search Result:")
for distance, idx in zip(distances[0], indices[0]):
    if idx < len(metadata):
        print(f"Distance: {distance}, Snippet: {metadata[idx]['snippet']}")
    else:
        print(f"Distance: {distance}, Snippet: Invalid Index {idx}")
