// Global variables at the top of the file
let currentConversationId = null;
let isProcessing = false;
let attachments = [];

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('send-button').addEventListener('click', sendMessage);
    document.getElementById('new-chat').addEventListener('click', createNewConversation);
    document.getElementById('clear-chat').addEventListener('click', clearChat);
    
    setupTextareaHandlers();
    setupConversationHandlers();
    setupFileInput();

    // Configure marked options for markdown
    marked.setOptions({
        highlight: function(code, language) {
            if (language && hljs.getLanguage(language)) {
                return hljs.highlight(code, { language: language }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true,
        gfm: true
    });

    // Set up handlers for existing conversations
    document.querySelectorAll('.conversation-item').forEach(item => {
        const conversationId = parseInt(item.dataset.id);
        
        // Add click handler for the conversation
        item.addEventListener('click', () => loadConversation(conversationId));
        
        // Add click handlers for buttons
        const editBtn = item.querySelector('.edit-conversation');
        if (editBtn) {
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                editConversationTitle(conversationId);
            });
        }
        
        const deleteBtn = item.querySelector('.delete-conversation');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteConversation(conversationId);
            });
        }
    });

    // Load the first conversation if it exists
    const firstConversation = document.querySelector('.conversation-item');
    if (firstConversation) {
        loadConversation(parseInt(firstConversation.dataset.id));
    }
});

// Setup handlers for textarea
function setupTextareaHandlers() {
    const textarea = document.getElementById('user-input');
    
    textarea.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    });
}

function setupConversationHandlers() {
    document.querySelectorAll('.conversation-item').forEach(item => {
        const conversationId = parseInt(item.dataset.id);
        
        // Remove existing listeners
        const newItem = item.cloneNode(true);
        item.parentNode.replaceChild(newItem, item);
        
        // Add conversation click handler
        newItem.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            loadConversation(conversationId);
        });
        
        // Add delete button handler
        const deleteBtn = newItem.querySelector('.delete-conversation');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                await deleteConversation(conversationId);
            });
        }
        
        // Add edit button handler
        const editBtn = newItem.querySelector('.edit-conversation');
        if (editBtn) {
            editBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                editConversationTitle(conversationId);
            });
        }
    });
}



async function loadConversation(conversationId) {
    try {
        // Clear current messages
        clearChat();
        
        // Update active conversation
        currentConversationId = conversationId;
        setActiveConversation(conversationId);
        
        // Fetch conversation messages
        const response = await fetch(`/conversation/${conversationId}`);
        if (!response.ok) {
            throw new Error('Failed to load conversation');
        }
        
        const messages = await response.json();
        
        // Clear messages again (in case any were added while fetching)
        document.getElementById('messages').innerHTML = '';
        
        // Sort messages by timestamp and ID
        messages.sort((a, b) => {
            const timeCompare = new Date(a.timestamp) - new Date(b.timestamp);
            return timeCompare !== 0 ? timeCompare : a.id - b.id;
        });
        
        // Display each message
        messages.forEach(message => {
            showMessage(message.content, message.role);
        });
        
        // Update conversation title
        const titleElement = document.getElementById('current-chat-title');
        const activeConversation = document.querySelector(`.conversation-item[data-id="${conversationId}"]`);
        if (titleElement && activeConversation) {
            titleElement.textContent = activeConversation.querySelector('.conversation-title').textContent;
        }
    } catch (error) {
        console.error('Error loading conversation:', error);
        displayError('Failed to load conversation');
    }
}

// Set active conversation
function setActiveConversation(id) {
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.toggle('active', item.dataset.id === String(id));
    });
}

// Add conversation to sidebar list
function addConversationToList(id, title) {
    const conversationsList = document.getElementById('conversations-list');
    
    const div = document.createElement('div');
    div.className = 'conversation-item';
    div.dataset.id = id;
    
    div.innerHTML = `
        <span class="conversation-title">${title}</span>
        <div class="conversation-actions">
            <button class="edit-conversation" data-id="${id}">
                <i class="fas fa-edit"></i>
            </button>
            <button class="delete-conversation" data-id="${id}">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `;
    
    // Add click handler for loading conversation
    div.addEventListener('click', () => loadConversation(id));
    
    // Add delete handler
    const deleteBtn = div.querySelector('.delete-conversation');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteConversation(id);
        });
    }
    
    // Add edit handler
    const editBtn = div.querySelector('.edit-conversation');
    if (editBtn) {
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            editConversationTitle(id);
        });
    }
    
    conversationsList.insertBefore(div, conversationsList.firstChild);
    setActiveConversation(id);
}

// Edit conversation title
async function editConversationTitle(id) {
    const conversationItem = document.querySelector(`.conversation-item[data-id="${id}"]`);
    const titleSpan = conversationItem.querySelector('.conversation-title');
    const currentTitle = titleSpan.textContent;
    
    const newTitle = prompt('Enter new conversation title:', currentTitle);
    if (newTitle && newTitle !== currentTitle) {
        try {
            const response = await fetch(`/conversation/${id}/title`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ title: newTitle })
            });
            
            if (!response.ok) {
                throw new Error('Failed to update title');
            }
            
            titleSpan.textContent = newTitle;
            
            // Update main title if this is the active conversation
            if (currentConversationId === id) {
                const mainTitle = document.getElementById('current-chat-title');
                if (mainTitle) {
                    mainTitle.textContent = newTitle;
                }
            }
        } catch (error) {
            console.error('Error updating title:', error);
            displayError('Failed to update conversation title');
        }
    }
}

// Delete conversation
async function deleteConversation(conversationId) {
    if (!confirm('Are you sure you want to delete this conversation?')) return;

    try {
        const response = await fetch(`/conversation/${conversationId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to delete conversation');
        }

        // Remove the conversation from the sidebar
        const element = document.querySelector(`.conversation-item[data-id="${conversationId}"]`);
        if (element) {
            element.remove();
        }

        // If this was the active conversation, clear the chat
        if (currentConversationId === conversationId) {
            currentConversationId = null;
            clearChat();
            document.getElementById('current-chat-title').textContent = 'Claude Chat';
        }

        // Try to load the first available conversation
        const firstConversation = document.querySelector('.conversation-item');
        if (firstConversation) {
            const firstConversationId = parseInt(firstConversation.dataset.id);
            loadConversation(firstConversationId);
        }

    } catch (error) {
        console.error('Error deleting conversation:', error);
        displayError(error.message);
    }
}

// Setup file input handlers
function setupFileInput() {
    const fileInput = document.getElementById('file-input');
    fileInput.addEventListener('change', handleFileSelect);
    
    const textarea = document.getElementById('user-input');
    textarea.addEventListener('paste', handlePaste);
    textarea.addEventListener('dragover', handleDragOver);
    textarea.addEventListener('dragleave', handleDragLeave);
    textarea.addEventListener('drop', handleDrop);
}

// File handling functions
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('dragover');
}

async function handleFileSelect(event) {
    const files = event.target.files;
    await addFiles(files);
    event.target.value = ''; // Reset file input
}

async function handlePaste(event) {
    const items = (event.clipboardData || event.originalEvent.clipboardData).items;
    const files = [];
    for (const item of items) {
        if (item.kind === 'file') {
            files.push(item.getAsFile());
        }
    }
    if (files.length > 0) {
        await addFiles(files);
    }
}

async function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.remove('dragover');
    const files = event.dataTransfer.files;
    await addFiles(files);
}

// Add files to attachments
async function addFiles(files) {
    const preview = document.getElementById('attachment-preview');
    
    for (const file of files) {
        if (file.size > MAX_FILE_SIZE) {
            displayError(`File ${file.name} exceeds maximum size of 10MB`);
            continue;
        }
        
        const attachment = {
            file: file,
            id: Date.now() + Math.random().toString(36)
        };
        
        attachments.push(attachment);
        
        const div = document.createElement('div');
        div.className = 'attachment-item';
        
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                div.innerHTML = `
                    <img src="${e.target.result}" class="attachment-preview-image">
                    <span>${file.name}</span>
                    <button class="remove-attachment" data-id="${attachment.id}">
                        <i class="fas fa-times"></i>
                    </button>
                `;
            };
            reader.readAsDataURL(file);
        } else {
            div.innerHTML = `
                <i class="fas fa-file-text"></i>
                <span>${file.name}</span>
                <button class="remove-attachment" data-id="${attachment.id}">
                    <i class="fas fa-times"></i>
                </button>
            `;
        }
        
        div.querySelector('.remove-attachment').addEventListener('click', () => {
            attachments = attachments.filter(a => a.id !== attachment.id);
            div.remove();
        });
        
        preview.appendChild(div);
    }
}

// Send message
async function sendMessage() {
    if (isProcessing) return;

    const input = document.getElementById('user-input');
    const message = input.value.trim();
    
    if (!message && attachments.length === 0) return;

    try {
        isProcessing = true;
        input.value = '';
        input.style.height = 'auto';

        const formData = new FormData();
        formData.append('message', message);
        if (currentConversationId) {
            formData.append('conversation_id', currentConversationId);
        }
        
        // Add attachments
        attachments.forEach(attachment => {
            formData.append('attachments[]', attachment.file);
        });

        // Display user message
        let userMessageContent = message;
        if (attachments.length > 0) {
            userMessageContent += '\n\nAttachments:\n' + 
                attachments.map(a => `- ${a.file.name}`).join('\n');
        }
        showMessage(userMessageContent, 'user');
        
        // Clear attachments preview
        document.getElementById('attachment-preview').innerHTML = '';
        attachments = [];
        
        // Show loading indicator
        const loadingDiv = createLoadingIndicator();
        document.getElementById('messages').appendChild(loadingDiv);

        const response = await fetch('/chat', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        loadingDiv.remove();

        if (data.error) {
            throw new Error(data.error);
        }

        // Update conversation ID if this is a new conversation
        if (!currentConversationId) {
            currentConversationId = data.conversation_id;
            // Reload the conversations list to show the new conversation
            window.location.reload();
        }

        showMessage(data.response, 'assistant');
        
    } catch (error) {
        displayError(error.message);
    } finally {
        isProcessing = false;
    }
}

// Create new conversation
async function createNewConversation() {
    try {
        const response = await fetch('/conversation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }

        addConversationToList(data.id, data.title);
        clearChat();
        
        return data.id;
    } catch (error) {
        console.error('Error creating conversation:', error);
        displayError(`Failed to create new conversation: ${error.message}`);
        throw error;
    }
}

// Show message
function showMessage(content, role) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    const iconDiv = document.createElement('div');
    iconDiv.className = 'message-icon';
    iconDiv.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Render markdown content
    contentDiv.innerHTML = marked.parse(content);
    
    // Add copy button to code blocks
    contentDiv.querySelectorAll('pre code').forEach((block) => {
        const pre = block.parentNode;
        const copyButton = document.createElement('button');
        copyButton.className = 'copy-code-button';
        copyButton.innerHTML = '<i class="fas fa-copy"></i>';
        copyButton.addEventListener('click', () => {
            navigator.clipboard.writeText(block.textContent);
            copyButton.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(() => {
                copyButton.innerHTML = '<i class="fas fa-copy"></i>';
            }, 2000);
        });
        pre.appendChild(copyButton);
    });
    
    messageDiv.appendChild(iconDiv);
    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);
    
    // Initialize syntax highlighting
    messageDiv.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightBlock(block);
    });
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Create loading indicator
function createLoadingIndicator() {
    const div = document.createElement('div');
    div.className = 'loading';
    div.innerHTML = `
        <div class="loading-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <span>Claude is thinking...</span>
    `;
    return div;
}

// Display error message
function displayError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error-message';
    errorDiv.textContent = `Error: ${message}`;
    document.getElementById('messages').appendChild(errorDiv);
}

// Clear chat
function clearChat() {
    document.getElementById('messages').innerHTML = '';
    document.getElementById('attachment-preview').innerHTML = '';
    attachments = [];
}

// Constants
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB