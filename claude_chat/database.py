import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = 'conversations.db'

    @contextmanager
    def get_db(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def cleanup_database(self):
        """Clean up any orphaned messages and fix conversation relationships."""
        try:
            with self.get_db() as conn:
                c = conn.cursor()
                
                # Delete messages that don't have a valid conversation
                c.execute('''
                    DELETE FROM messages 
                    WHERE conversation_id NOT IN (
                        SELECT id FROM conversations
                    )
                ''')
                
                # Delete duplicate messages within the same conversation
                c.execute('''
                    DELETE FROM messages 
                    WHERE id NOT IN (
                        SELECT MIN(id)
                        FROM messages
                        GROUP BY conversation_id, role, content, timestamp
                    )
                ''')
                
                conn.commit()
                logger.info("Database cleanup completed")
        except Exception as e:
            logger.error(f"Failed to cleanup database: {e}")
            raise

    def init_db(self):
        try:
            with self.get_db() as conn:
                c = conn.cursor()
                
                # Create conversations table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_archived BOOLEAN DEFAULT 0
                    )
                ''')
                
                # Create messages table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id INTEGER,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                self.cleanup_database()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_conversations(self):
        """Retrieve all active conversations."""
        try:
            with self.get_db() as conn:
                conversations = conn.execute('''
                    SELECT * FROM conversations 
                    WHERE NOT is_archived 
                    ORDER BY updated_at DESC
                ''').fetchall()
                return [dict(conv) for conv in conversations]
        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            return []

    def get_conversation_messages(self, conversation_id):
        """Retrieve all messages for a specific conversation."""
        try:
            with self.get_db() as conn:
                # Use a subquery to get only the latest version of each message
                messages = conn.execute('''
                    WITH RankedMessages AS (
                        SELECT 
                            id,
                            conversation_id,
                            role,
                            content,
                            timestamp,
                            ROW_NUMBER() OVER (
                                PARTITION BY conversation_id, role, content 
                                ORDER BY timestamp DESC, id DESC
                            ) as rn
                        FROM messages
                        WHERE conversation_id = ?
                    )
                    SELECT 
                        id,
                        conversation_id,
                        role,
                        content,
                        timestamp
                    FROM RankedMessages
                    WHERE rn = 1
                    ORDER BY timestamp ASC, id ASC
                ''', (conversation_id,)).fetchall()
                
                return [dict(msg) for msg in messages]
        except Exception as e:
            logger.error(f"Failed to get conversation messages: {e}")
            return []

    def create_conversation(self, title):
        try:
            with self.get_db() as conn:
                c = conn.cursor()
                c.execute(
                    'INSERT INTO conversations (title) VALUES (?)',
                    (title,)
                )
                conversation_id = c.lastrowid
                conn.commit()
                logger.info(f"Created new conversation with ID: {conversation_id}")
                return conversation_id
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise

    def add_message(self, conversation_id, role, content):
        """Add a message to a specific conversation."""
        try:
            with self.get_db() as conn:
                # First verify the conversation exists
                conv = conn.execute(
                    'SELECT id FROM conversations WHERE id = ?', 
                    (conversation_id,)
                ).fetchone()
                
                if not conv:
                    raise Exception(f"Conversation {conversation_id} does not exist")

                current_time = datetime.now().isoformat()
                
                # Check for duplicate messages in this conversation
                existing = conn.execute('''
                    SELECT id FROM messages 
                    WHERE conversation_id = ? AND role = ? AND content = ?
                    ORDER BY timestamp DESC LIMIT 1
                ''', (conversation_id, role, content)).fetchone()
                
                if not existing:
                    c = conn.cursor()
                    c.execute('''
                        INSERT INTO messages (conversation_id, role, content, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (conversation_id, role, content, current_time))
                    
                    # Update conversation timestamp
                    c.execute('''
                        UPDATE conversations 
                        SET updated_at = ? 
                        WHERE id = ?
                    ''', (current_time, conversation_id))
                    
                    conn.commit()
                    logger.info(f"Added message to conversation {conversation_id}")
                else:
                    logger.info(f"Skipped duplicate message in conversation {conversation_id}")
                    
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            raise

    def delete_conversation(self, conversation_id):
        """Delete a conversation and its messages."""
        try:
            with self.get_db() as conn:
                c = conn.cursor()
                # First delete all messages associated with the conversation
                c.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
                # Then delete the conversation itself
                c.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
                conn.commit()
                logger.info(f"Deleted conversation {conversation_id} and its messages")
                return True
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False

    def update_conversation_title(self, conversation_id, title):
        try:
            with self.get_db() as conn:
                c = conn.cursor()
                c.execute('''
                    UPDATE conversations 
                    SET title = ? 
                    WHERE id = ?
                ''', (title, conversation_id))
                conn.commit()
                logger.info(f"Updated title for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to update conversation title: {e}")
            raise

    def cleanup_duplicate_messages(self):
        """Remove duplicate messages from the database."""
        try:
            with self.get_db() as conn:
                c = conn.cursor()
                # Delete duplicate messages keeping only the latest version
                c.execute('''
                    DELETE FROM messages 
                    WHERE id NOT IN (
                        SELECT MAX(id)
                        FROM messages
                        GROUP BY conversation_id, role, content, timestamp
                    )
                ''')
                conn.commit()
                logger.info("Cleaned up duplicate messages")
        except Exception as e:
            logger.error(f"Failed to cleanup duplicate messages: {e}")

db = Database()