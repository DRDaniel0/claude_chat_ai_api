from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import anthropic
import logging
import base64
import os
import mimetypes
from PIL import Image
from io import BytesIO
from database import db
from config import Config
from utils import truncate_messages_to_token_limit, format_error_message
from datetime import datetime

# Initialize Flask app
# Update the Flask app initialization
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Anthropic client
client = anthropic.Client(api_key=Config.ANTHROPIC_API_KEY)

# Initialize database
db.init_db()

# File handling configurations
ALLOWED_TEXT_EXTENSIONS = {
    '.txt', '.py', '.js', '.html', '.css', '.json', '.xml', 
    '.md', '.csv', '.log', '.yml', '.yaml', '.sh', '.bash',
    '.env', '.conf', '.cfg', '.ini', '.sql', '.r', '.ruby',
    '.php', '.java', '.cpp', '.c', '.h', '.hpp', '.cs'
}

ALLOWED_IMAGE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename, allowed_extensions):
    return get_file_extension(filename) in allowed_extensions

def is_image_file(filename):
    return get_file_extension(filename) in ALLOWED_IMAGE_EXTENSIONS

def is_text_file(filename):
    return get_file_extension(filename) in ALLOWED_TEXT_EXTENSIONS

def process_image(file):
    """Process and optimize image for Claude."""
    try:
        image = Image.open(file)
        
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        # Resize if too large while maintaining aspect ratio
        max_dimension = 2048
        if max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Save to BytesIO
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=85, optimize=True)
        buffer.seek(0)
        
        # Convert to base64
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
            'type': 'image',
            'data': image_base64
        }
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise

def process_text_file(file):
    """Process text file content."""
    try:
        content = file.read().decode('utf-8', errors='ignore')
        ext = get_file_extension(file.filename)[1:]  # Remove the dot
        return {
            'type': 'text',
            'filename': file.filename,
            'extension': ext,
            'content': content
        }
    except Exception as e:
        logger.error(f"Error processing text file: {e}")
        raise

# ... [rest of the routes remain the same]

# Add these before the main route
@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', conversations=[]), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', conversations=[]), 500

# ... [previous imports and configurations remain the same] ...

# Add this after the error handlers and before the chat route
@app.route('/')
def home():
    try:
        # Clean up any duplicate messages
        db.cleanup_duplicate_messages()
        conversations = db.get_conversations()
        return render_template('index.html', conversations=conversations)
    except Exception as e:
        logger.error(f"Error in home route: {e}")
        return render_template('index.html', conversations=[])

@app.route('/conversations', methods=['GET'])
def get_all_conversations():
    try:
        conversations = db.get_conversations()
        return jsonify(conversations)
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({'error': 'Failed to retrieve conversations'}), 500

@app.route('/conversation', methods=['POST'])
def create_new_conversation():
    try:
        title = request.json.get('title', f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        conversation_id = db.create_conversation(title)
        logger.info(f"Successfully created conversation: {conversation_id}")
        return jsonify({'id': conversation_id, 'title': title})
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/conversation/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    try:
        messages = db.get_conversation_messages(conversation_id)
        return jsonify(messages)
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {e}")
        return jsonify({'error': 'Failed to retrieve conversation'}), 500

@app.route('/conversation/<int:conversation_id>', methods=['DELETE'])
def delete_conv(conversation_id):
    try:
        success = db.delete_conversation(conversation_id)
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'Failed to delete conversation'}), 500
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/conversation/<int:conversation_id>/title', methods=['PUT'])
def update_conversation_title(conversation_id):
    try:
        new_title = request.json.get('title')
        if not new_title:
            return jsonify({'error': 'Title is required'}), 400
        
        db.update_conversation_title(conversation_id, new_title)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error updating conversation title {conversation_id}: {e}")
        return jsonify({'error': 'Failed to update conversation title'}), 500

# ... [chat route and rest of the code remains the same] ...

@app.route('/chat', methods=['POST'])
def chat():
    try:
        db.cleanup_duplicate_messages()
        conversation_id = request.form.get('conversation_id')
        message = request.form.get('message', '')
        files = request.files.getlist('attachments[]')
        
        # Create new conversation if no ID provided or if it's a new chat
        if not conversation_id or conversation_id == 'null':
            conversation_id = db.create_conversation(f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        else:
            # Verify existing conversation
            conversations = db.get_conversations()
            if not any(str(conv['id']) == str(conversation_id) for conv in conversations):
                return jsonify({'error': 'Invalid conversation ID'}), 400
            
            # Convert conversation_id to integer
            conversation_id = int(conversation_id)
        
        # Process files
        processed_files = []
        for file in files:
            if file and file.filename:
                # Check file size
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                
                if size > MAX_FILE_SIZE:
                    return jsonify({
                        'error': f'File {file.filename} exceeds maximum size of 10MB'
                    }), 400
                
                if is_image_file(file.filename):
                    processed_files.append(process_image(file))
                elif is_text_file(file.filename):
                    processed_files.append(process_text_file(file))
                else:
                    return jsonify({
                        'error': f'File {file.filename} is not a supported file type'
                    }), 400

        # Prepare message with files
        full_message = message if message else ""
        
        # Add text file contents
        for file in processed_files:
            if file['type'] == 'text':
                full_message += f"\nFile: {file['filename']}\n```{file['extension']}\n{file['content']}\n```\n"

        # Save user message
        db.add_message(conversation_id, 'user', full_message)
        
        # Get conversation history
        messages = db.get_conversation_messages(conversation_id)
        
        # Format messages for Claude
        claude_messages = [
            {'role': msg['role'], 'content': msg['content']} 
            for msg in messages
        ]
        
        # Add images as separate messages if present
        image_files = [f for f in processed_files if f['type'] == 'image']
        if image_files:
            for img in image_files:
                claude_messages.append({
                    'role': 'user',
                    'content': f"<image>{img['data']}</image>"
                })
        
        logger.debug(f"Sending request to Claude with {len(claude_messages)} messages")
        
        # Get response from Claude
        response = client.messages.create(
            model=Config.MODEL_NAME,
            max_tokens=Config.DEFAULT_MAX_TOKENS,
            messages=claude_messages,
            temperature=0.7
        )
        
        assistant_message = response.content[0].text
        
        # Save assistant message
        db.add_message(conversation_id, 'assistant', assistant_message)
        
        return jsonify({
            'response': assistant_message,
            'conversation_id': conversation_id
        })
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        error_message = format_error_message(e)
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':
    # Initialize database
    try:
        db.init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Configuration for running the app
    app_config = {
        'host': '0.0.0.0',
        'port': 5001,
        'debug': True
    }
    
    logger.info(f"Starting application with config: {app_config}")
    app.run(**app_config)