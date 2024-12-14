import os
import fitz  # PyMuPDF
import unicodedata
import json

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    page_texts = {}  # Dictionary to hold page number and text
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        page_text = page.get_text()
        page_text = normalize_text(page_text)
        page_texts[page_num + 1] = page_text  # Page numbers start from 1
    return page_texts

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

def extract_text_from_pdfs(pdf_directory):
    pdf_texts = {}  # Dictionary to hold PDF filename and page texts
    # Traverse the directory to find all PDF files
    for root, dirs, files in os.walk(pdf_directory):
        for file in files:
            if file.endswith('.pdf'):
                pdf_path = os.path.join(root, file)
                print(f"Extracting text from: {pdf_path}")
                page_texts = extract_text_from_pdf(pdf_path)
                if page_texts:
                    relative_pdf_path = os.path.relpath(pdf_path, pdf_directory)
                    pdf_filename = relative_pdf_path.replace(os.sep, '/')
                    pdf_texts[pdf_filename] = page_texts
                else:
                    print(f"No text extracted from {pdf_path}")
    return pdf_texts

# Example usage
pdf_directory = '/Users/vbamba/Projects/collectedworks/pdfs'  # Path to your PDFs

pdf_texts = extract_text_from_pdfs(pdf_directory)

# Optionally, save the extracted texts to a JSON file for later use
with open('extracted_texts.json', 'w', encoding='utf-8') as f:
    json.dump(pdf_texts, f, ensure_ascii=False, indent=4)
