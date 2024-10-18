import sys
import os
import faiss
import numpy as np
import re
from sentence_transformers import SentenceTransformer
import unicodedata
import json

# Initialize the SentenceTransformer model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')


def chunk_text_with_chapters(text, chunk_size=1000, overlap=200):
    # Define the regex pattern
    chapter_pattern = re.compile(
        r'''
        ^(                                # Start of line
            (?:Chapter\s+\w+.*)            # Matches 'Chapter I', 'Chapter 1', etc.
            |                              # OR
            (?:PART\s+\w+.*)               # Matches 'PART I', 'PART 1', etc.
            |                              # OR
            (?:BOOK\s+\w+.*)               # Matches 'BOOK II', 'BOOK 2', etc.
            |                              # OR
            (?:[A-Z][A-Z\s\-',:&]+)        # Matches lines in all uppercase letters
        )$
        ''', re.VERBOSE | re.MULTILINE
    )

    lines = text.split('\n')
    chunks = []
    chapter_titles = []

    current_chapter_title = 'Introduction'  # Default title if none is found
    current_text = ''

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if chapter_pattern.match(line_stripped):
            # If there's accumulated text, chunk it and reset
            if current_text:
                chunked_texts = chunk_text(current_text, chunk_size, overlap)
                chunks.extend(chunked_texts)
                chapter_titles.extend([current_chapter_title] * len(chunked_texts))
                current_text = ''
            # Set the new chapter title
            current_chapter_title = line_stripped
            # Check if the next line is a subheading (e.g., the actual chapter title)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.isdigit() and not chapter_pattern.match(next_line):
                    current_chapter_title += ' - ' + next_line
        elif line_stripped.isdigit():
            # Ignore page numbers
            continue
        else:
            current_text += line + ' '

    # Handle any remaining text
    if current_text:
        chunked_texts = chunk_text(current_text, chunk_size, overlap)
        chunks.extend(chunked_texts)
        chapter_titles.extend([current_chapter_title] * len(chunked_texts))

    return chunks, chapter_titles


def get_embedding(text):
    # Generate embedding using Hugging Face model
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding


def chunk_text(text, chunk_size=1000, overlap=200):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks


def normalize_text(text):
    # Normalize Unicode characters to their canonical forms
    text = unicodedata.normalize('NFKC', text)
    # Replace specific ligature characters if needed
    ligatures = {
        'ﬁ': 'fi',
        'ﬂ': 'fl',
        'ﬀ': 'ff',
        'ﬃ': 'ffi',
        'ﬄ': 'ffl',
        'ﬅ': 'st',
        'ﬆ': 'st',
        '\ufb01': 'fi',
        '\ufb02': 'fl',
    }
    for ligature, replacement in ligatures.items():
        text = text.replace(ligature, replacement)
    return text


def get_pdf_url(text_file_path, text_directory, pdf_base_url='https://127.0.0.1:5000/pdfs/'):
    """
    Maps a text file path to its corresponding PDF URL.
    """
    # Determine the relative path of the text file with respect to the text_directory
    relative_path = os.path.relpath(text_file_path, text_directory)
    # Replace the .txt extension with .pdf
    relative_pdf_path = relative_path.replace('.txt', '.pdf')
    # Construct the PDF URL
    pdf_url = os.path.join(pdf_base_url, relative_pdf_path).replace("\\", "/")  # Ensure URL uses forward slashes
    return pdf_url


def create_embeddings_from_texts(text_directory, pdf_directory, index_output_dir, chunk_size=1000, overlap=200, pdf_base_url='https://yourdomain.com/pdfs/'):
    embeddings = []
    metadata = []  # To store chapter and file details

    # Traverse the directory to find all text files
    for root, dirs, files in os.walk(text_directory):
        for file in files:
            if file.endswith('.txt'):
                text_file_path = os.path.join(root, file)
                with open(text_file_path, 'r', encoding='utf-8') as text_file:
                    text = text_file.read()
                # Preprocess text
                text = normalize_text(text)  # Normalize text to fix encoding issues
                text = text.replace('-\n', '')  # Remove hyphens at line breaks

                # Use the chunking function
                chunks, chapter_titles = chunk_text_with_chapters(text, chunk_size, overlap)

                # Generate embedding for each chunk
                for chunk_num, (chunk, chapter_title) in enumerate(zip(chunks, chapter_titles)):
                    print(f"Generating embedding for chunk {chunk_num} of: {text_file_path}")
                    embedding = get_embedding(chunk)
                    embeddings.append(embedding)

                    # Map text file to PDF URL
                    pdf_url = get_pdf_url(text_file_path, text_directory, pdf_base_url)

                    # Add file path and chapter metadata
                    file_metadata = {
                        'file_path': text_file_path,  # Original text file path
                        'pdf_url': pdf_url,            # Corresponding PDF URL
                        'chapter_name': chapter_title,
                        'snippet': chunk,  # Store full chunk or adjust as needed
                        'page_number': chunk_num + 1  # Approximate page number or chunk number
                    }
                    metadata.append(file_metadata)

    # Convert embeddings to numpy array
    embeddings_np = np.array(embeddings).astype('float32')

    # Create FAISS index
    index = faiss.IndexFlatL2(embeddings_np.shape[1])  # L2 distance metric
    index.add(embeddings_np)  # Add embeddings to the FAISS index

    # Normalize embeddings for cosine similarity
    # faiss.normalize_L2(embeddings_np)
    # Create IndexFlatIP
    # index = faiss.IndexFlatIP(embeddings_np.shape[1])
    # index.add(embeddings_np)


    # Create directory if it doesn't exist
    os.makedirs(index_output_dir, exist_ok=True)

    # Save the FAISS index and metadata to files
    faiss.write_index(index, os.path.join(index_output_dir, 'faiss_index.bin'))
    # Ensure metadata is JSON serializable (convert numpy types if necessary)
    with open(os.path.join(index_output_dir, 'metadata.json'), 'w', encoding='utf-8') as meta_file:
        json.dump(metadata, meta_file, ensure_ascii=False, indent=2)
    print(f"FAISS index and metadata saved in {index_output_dir}")


# Example usage
if __name__ == "__main__":
    text_directory = '/Users/vbamba/Projects/collectedworks/text'  
    pdf_directory = '/Users/vbamba/Projects/collectedworks/pdfs'  
    index_output_dir = '/Users/vbamba/Projects/collectedworks/indexes'
    pdf_base_url = 'http://127.0.0.1:5000/pdfs/'  # Adjust based on server setup

    create_embeddings_from_texts(
        text_directory, 
        pdf_directory, 
        index_output_dir, 
        chunk_size=1000, 
        overlap=200, 
        pdf_base_url=pdf_base_url
    )
