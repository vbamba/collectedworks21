# CollectedWorks Project

## Overview

A Flask and React-based application for searching and filtering PDF documents using FAISS indexing.

## Project Structure

/collectedworks_new ├── /backend │ ├── /app │ │ ├── init.py │ │ ├── routes.py │ ├── /scripts │ ├── /pdf │ ├── /indexes │ ├── requirements.txt │ └── app.py ├── /frontend │ ├── /public │ ├── /src │ │ ├── /components │ │ ├── /pages │ │ ├── /services │ │ ├── App.js │ │ └── index.js │ ├── package.json │ └── ... ├── README.md └── .gitignore

markdown
Copy code

## Setup Instructions

### Backend

1. **Navigate to Backend Directory:**

cd backend
Create and Activate Conda Environment:


conda create -n collectedworks_env python=3.12
conda activate collectedworks_env

Upgrade pip and setuptools:


pip install --upgrade pip setuptools
Install Dependencies:


pip install -r requirements.txt

Run the Backend Server:


python app.py
Frontend
Navigate to Frontend Directory:


cd frontend
Install Dependencies:


npm install
Configure Environment Variables:

Create a .env file with the following content:

env

REACT_APP_BACKEND_URL=http://127.0.0.1:5001

Run the Frontend Server:


npm start

Usage
Access the frontend at http://localhost:3000.

Use the search bar and filters to query PDF documents.
Toggle dark mode using the provided button.

Testing
Backend

pytest backend/tests/

Frontend

npm test