from app import create_app
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = create_app()

if __name__ == "__main__":
    # Get port from environment or use default
    port = int(os.getenv("PORT", 5000))
    
    logger.info(f"🚀 Starting Stewardship System on port {1234}")
    logger.info(f"📊 Database: PostgreSQL")
    logger.info(f"🌐 URL: http://localhost:{1234}")
    
    app.run(host="0.0.0.0", port=5000, debug=True)