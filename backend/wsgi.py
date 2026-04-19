# backend/app.py
from app import create_app
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

app = create_app()
app.config['JSON_AS_ASCII'] = False

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
