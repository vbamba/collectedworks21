
import os
import json
import re

# Set the root directory and the output JSON file
root_dir = "/Users/vbamba/Projects/collectedworks21/backend/pdf"
output_file = "book_mapping.json"

# Function to create a readable book title from file name
def format_title(file_name):
    # Remove file extension and any numbers or hyphens at the beginning
    title = re.sub(r'^[0-9]+[-_]*', '', file_name.replace('.pdf', ''))
    # Insert spaces before capital letters and capitalize each word
    title = re.sub(r'([a-z])([A-Z])', r'\1 \2', title).replace('_', ' ').replace('-', ' ')
    return title.title()

# Function to determine group, description, and capitalize author based on folder name
def get_folder_details(folder_name):
    folder_name_lower = folder_name.lower()
    if folder_name_lower == "sriaurobindo":
        return "CWSA", "An extensive account of spiritual experiences and teachings of Sri Aurobindo.", folder_name.capitalize()
    elif folder_name_lower == "mother":
        return "CWM", "An extensive account of spiritual experiences and teachings of The Mother", folder_name.capitalize()
    elif folder_name_lower == "disciples":
        return "Disciples", "", folder_name.capitalize()
    else:
        return "CWSA", "", folder_name.capitalize()  # Default to CWSA if folder is unspecified

# Initialize a dictionary to store the book mapping
book_mapping = {}

# Traverse the directory structure
for root, dirs, files in os.walk(root_dir):
    author = os.path.basename(root)  # Assume author is the name of the subfolder
    group, description, capitalized_author = get_folder_details(author)
    for file_name in files:
        if file_name.endswith(".pdf"):
            # Construct the entry for each PDF file
            entry = {
                "book_title": format_title(file_name),
                "author": capitalized_author,
                "group": group,
                "priority": 99,
                "language": "English",
                "isbn": "",
                "tags": ["Yoga", "Philosophy", "Spirituality"],
                "format": "PDF",
                "availability": "Public",
                "description": description
            }
            # Add the entry to the book mapping
            book_mapping[file_name] = entry

# Write the book mapping to the JSON file
with open(output_file, "w") as json_file:
    json.dump(book_mapping, json_file, indent=4)

print(f"Book mapping generated and saved to {output_file}")
