import tiktoken
from typing import List, Dict

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def truncate_messages_to_token_limit(messages: List[Dict], max_tokens: int) -> List[Dict]:
    """Truncate messages to fit within token limit while maintaining newest messages."""
    total_tokens = 0
    truncated_messages = []
    
    for message in reversed(messages):
        message_tokens = estimate_tokens(message['content'])
        if total_tokens + message_tokens > max_tokens:
            break
        truncated_messages.insert(0, message)
        total_tokens += message_tokens
    
    return truncated_messages

def format_error_message(error: Exception) -> str:
    """Format error messages for client display."""
    if "rate limit" in str(error).lower():
        return "Rate limit exceeded. Please wait a moment and try again."
    elif "maximum context length" in str(error).lower():
        return "The conversation is too long. Please start a new one."
    else:
        return f"An error occurred: {str(error)}"