import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import unicodedata
import logging
import fitz  # PyMuPDF

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("embedding.log"),
        logging.StreamHandler()
    ]
)

# Load the Hugging Face model
logging.info("Loading SentenceTransformer model...")
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
logging.info("Model loaded successfully.")

def normalize_text(text):
    # Normalize Unicode characters to their canonical forms
    text = unicodedata.normalize('NFKC', text)
    # Replace specific ligature characters
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
    # Replace curly quotes and other special characters
    curly_quotes = {
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
        '–': '-',   # En dash
        '—': '-',   # Em dash
        '…': '...', # Ellipsis
        '′': "'",   # Prime
        '″': '"',   # Double Prime
    }
    for curly, straight in curly_quotes.items():
        text = text.replace(curly, straight)
    return text

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from each page of the PDF using fitz (PyMuPDF).
    Returns a dictionary with page numbers as keys and text as values.
    """
    page_texts = {}
    page_headings = {}
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")  # Extract text as plain text
            text = normalize_text(text)
            page_texts[page_num + 1] = text  # Pages are 1-indexed

            # Simple heuristic for headings: lines in uppercase or larger font size
            # This can be enhanced based on specific PDF structures
            headings = []
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block['type'] == 0:  # text block
                    for line in block["lines"]:
                        spans = line["spans"]
                        for span in spans:
                            if span["size"] >= 14 and span["text"].strip().isupper():
                                headings.append(span["text"].strip())
            chapter_name = ' | '.join(headings) if headings else ''
            page_headings[page_num + 1] = chapter_name
    except Exception as e:
        logging.error(f"Error extracting from PDF {pdf_path}: {e}")
    return page_texts, page_headings

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

def get_pdf_url_from_pdf_path(pdf_file_path, pdf_directory, base_pdf_url):
    """
    Generate the PDF URL corresponding to a given PDF file path.
    """
    # Determine the relative path of the PDF file with respect to the pdf_directory
    relative_pdf_path = os.path.relpath(pdf_file_path, pdf_directory)
    # Construct the PDF URL
    pdf_url = os.path.join(base_pdf_url, relative_pdf_path.replace(os.sep, '/'))
    return pdf_url

def create_embeddings_from_pdfs(pdf_directory, index_output_dir, base_pdf_url, book_mapping_path, chunk_size=1000, overlap=200):
    embeddings = []
    metadata = []  # To store chapter and file details
    total_pdfs = 0
    total_pages = 0
    total_chunks = 0

    # Load book mappings
    try:
        with open(book_mapping_path, 'r', encoding='utf-8') as bm_file:
            book_mapping = json.load(bm_file)
        logging.info("Book mapping loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading book mapping from {book_mapping_path}: {e}")
        return

    # Traverse the directory to find all PDF files
    for root, dirs, files in os.walk(pdf_directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_file_path = os.path.join(root, file)
                logging.info(f"Processing PDF: {pdf_file_path}")
                total_pdfs += 1

                # Extract text and headings from the PDF using fitz
                page_texts, page_headings = extract_text_from_pdf(pdf_file_path)
                num_pages = len(page_texts)
                total_pages += num_pages
                logging.info(f"Extracted text from {num_pages} pages.")

                # Generate the PDF URL
                pdf_url = get_pdf_url_from_pdf_path(pdf_file_path, pdf_directory, base_pdf_url)
                # Use only the basename (filename without directories) for mapping
                pdf_filename = os.path.basename(pdf_file_path)

                # Retrieve book info from mapping
                book_info = book_mapping.get(pdf_filename, {"book_title": "Unknown", "author": "Unknown", "group": "Unknown", "priority": 999})
                book_title = book_info.get("book_title", "Unknown")
                author = book_info.get("author", "Unknown")
                group = book_info.get("group", "Unknown")
                priority = book_info.get("priority", 999)

                # Process each page
                for page_number, page_text in page_texts.items():
                    # Get headings for this page
                    chapter_name = page_headings.get(page_number, '')
                    # Split page text into chunks if needed
                    chunks = chunk_text(page_text, chunk_size, overlap)
                    num_chunks = len(chunks)
                    total_chunks += num_chunks
                    logging.info(f"Page {page_number}: {num_chunks} chunks created.")

                    for chunk_num, chunk in enumerate(chunks):
                        logging.debug(f"Generating embedding for {pdf_filename}, page {page_number}, chunk {chunk_num}")
                        embedding = get_embedding(chunk)
                        embeddings.append(embedding)

                        pdf_url_with_page = f"{pdf_url}#page={page_number}"

                        # Add file path, PDF URL with page, book title, author, group, priority, and chapter metadata
                        file_metadata = {
                            'file_path': pdf_file_path,
                            'pdf_url': pdf_url_with_page,
                            'book_title': book_title,
                            'author': author,
                            'group': group,
                            'priority': priority,
                            'chapter_name': chapter_name,
                            'snippet': chunk,
                            'page_number': page_number
                        }
                        metadata.append(file_metadata)

    logging.info(f"Total PDFs processed: {total_pdfs}")
    logging.info(f"Total pages processed: {total_pages}")
    logging.info(f"Total chunks created: {total_chunks}")

    # Convert embeddings to numpy array
    try:
        embeddings_np = np.array(embeddings).astype('float32')
        #normalize  both your embeddings and query vectors to unit length. This allows the inner product to effectively represent cosine similarity.
        faiss.normalize_L2(embeddings_np)       
        logging.info(f"Embeddings shape: {embeddings_np.shape}")
    except Exception as e:
        logging.error(f"Error converting embeddings to numpy array: {e}")
        return

    # Create FAISS index
    if embeddings_np.size > 0:
        try:
            #index = faiss.IndexFlatL2(embeddings_np.shape[1])  # L2 distance metric
            # Use IndexFlatIP using Inner Product for cosine similarity
            index = faiss.IndexFlatIP(embeddings_np.shape[1])            
            index.add(embeddings_np)  # Add embeddings to the FAISS index
            logging.info(f"FAISS index created with {index.ntotal} embeddings.")
        except Exception as e:
            logging.error(f"Error creating FAISS index: {e}")
            return

        # Create directory if it doesn't exist
        try:
            os.makedirs(index_output_dir, exist_ok=True)
            logging.info(f"Index output directory created at {index_output_dir}.")
        except Exception as e:
            logging.error(f"Error creating index output directory: {e}")
            return

        # Save the FAISS index
        try:
            faiss.write_index(index, os.path.join(index_output_dir, 'faiss_index.bin'))
            logging.info("FAISS index saved successfully.")
        except Exception as e:
            logging.error(f"Error saving FAISS index: {e}")
            return

        # Save metadata as JSON
        try:
            with open(os.path.join(index_output_dir, 'metadata.json'), 'w', encoding='utf-8') as meta_file:
                json.dump(metadata, meta_file, ensure_ascii=False, indent=4)
            logging.info("Metadata saved successfully.")
        except Exception as e:
            logging.error(f"Error saving metadata: {e}")
            return
    else:
        logging.warning("No embeddings were generated. Please check your PDFs and extraction process.")

# Example usage
if __name__ == "__main__":
    pdf_directory = '/Users/vbamba/Projects/collectedworks21/backend/pdf'
    index_output_dir = '/Users/vbamba/Projects/collectedworks21/backend/indexes'
    base_pdf_url = 'http://127.0.0.1:5001/pdfs'  # Adjust based on your server's URL
    book_mapping_path = os.path.join(index_output_dir, 'book_mapping.json')

    # Create the FAISS index with chunking
    create_embeddings_from_pdfs(
        pdf_directory=pdf_directory,
        index_output_dir=index_output_dir,
        base_pdf_url=base_pdf_url,
        book_mapping_path=book_mapping_path,
        chunk_size=1000,
        overlap=200
    )
