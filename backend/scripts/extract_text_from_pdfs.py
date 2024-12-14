import os
import sys
import unicodedata
import json
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTTextLine
from collections import defaultdict

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
    return text

def extract_text_and_headings_from_pdf(pdf_path):
    page_texts = {}  # Dictionary to hold page number and text
    page_headings = {}  # Dictionary to hold page number and headings
    for page_layout in extract_pages(pdf_path):
        page_num = page_layout.pageid  # pdfminer starts page numbering from 1
        page_text = ''
        page_headings_list = []
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                for text_line in element:
                    if isinstance(text_line, LTTextLine):
                        line_text = text_line.get_text()
                        # Analyze font sizes
                        font_sizes = []
                        for char in text_line:
                            if isinstance(char, LTChar):
                                font_sizes.append(char.size)
                        if font_sizes:
                            avg_font_size = sum(font_sizes) / len(font_sizes)
                            # Set a threshold for heading detection
                            # Adjust the thresholds based on your PDFs
                            if avg_font_size >= 14:
                                # Assume this is a heading
                                heading_text = line_text.strip()
                                page_headings_list.append(heading_text)
                        page_text += line_text
        page_text = normalize_text(page_text)
        page_texts[page_num] = page_text
        page_headings[page_num] = page_headings_list
    return page_texts, page_headings

def extract_text_from_pdfs(pdf_directory):
    pdf_texts = {}     # Dictionary to hold PDF filename and page texts
    pdf_headings = {}  # Dictionary to hold PDF filename and headings
    # Traverse the directory to find all PDF files
    for root, dirs, files in os.walk(pdf_directory):
        for file in files:
            if file.endswith('.pdf'):
                pdf_path = os.path.join(root, file)
                print(f"Extracting text from: {pdf_path}")
                page_texts, page_headings = extract_text_and_headings_from_pdf(pdf_path)
                if page_texts:
                    relative_pdf_path = os.path.relpath(pdf_path, pdf_directory)
                    pdf_filename = relative_pdf_path.replace(os.sep, '/')
                    pdf_texts[pdf_filename] = page_texts
                    pdf_headings[pdf_filename] = page_headings
                else:
                    print(f"No text extracted from {pdf_path}")
    return pdf_texts, pdf_headings

# Example usage
pdf_directory = '/Users/vbamba/Projects/collectedworks/pdfs'  # Replace with your PDFs directory

pdf_texts, pdf_headings = extract_text_from_pdfs(pdf_directory)

# Optionally, save the extracted texts and headings to JSON files for later use
with open('extracted_texts.json', 'w', encoding='utf-8') as f:
    json.dump(pdf_texts, f, ensure_ascii=False, indent=4)

with open('extracted_headings.json', 'w', encoding='utf-8') as f:
    json.dump(pdf_headings, f, ensure_ascii=False, indent=4)
