import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    DATABASE_PATH = 'conversations.db'
    MAX_TOKENS = 4096  # Updated to match Claude-3-Sonnet limit
    MESSAGES_LIMIT = 50
    MODEL_NAME = "claude-3-sonnet-20240229"
    DEFAULT_MAX_TOKENS = 4096  # Updated to match model limit
    
    # Server configuration
    HOST = '0.0.0.0'
    PORT = 5001
    DEBUG = True
    
    # CORS settings
    CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5000']
    
    # Logging configuration
    LOG_LEVEL = 'DEBUG'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'app.log'