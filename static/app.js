// Initialize UI Elements
const messagesContainer = document.getElementById('messages-container');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');
const currentModelDisplay = document.getElementById('current-model-display');
const clearChatBtn = document.getElementById('clear-chat-btn');
const configWarning = document.getElementById('config-warning');
const customModelWrapper = document.getElementById('custom-model-wrapper');
const customModelInput = document.getElementById('custom-model-input');

// State Management
let chatHistory = [];
let isGenerating = false;

// Initialize Lucide Icons
lucide.createIcons();

// Auto-configure Marked.js to parse breaks
if (typeof marked !== 'undefined') {
    marked.use({
        breaks: true,
        gfm: true
    });
}

// Check Backend Config on Load
async function checkConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            if (!config.api_key_configured) {
                configWarning.classList.remove('hidden');
            } else {
                configWarning.classList.add('hidden');
            }
            if (config.default_model) {
                const hasOption = Array.from(modelSelect.options).some(opt => opt.value === config.default_model);
                if (hasOption) {
                    modelSelect.value = config.default_model;
                } else {
                    modelSelect.value = 'custom';
                    customModelInput.value = config.default_model;
                }
                updateModelDisplay();
            }
        }
    } catch (error) {
        console.error('Error fetching backend config:', error);
    }
}

// Adjust Textarea Height automatically
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = `${Math.min(userInput.scrollHeight - 12, 150)}px`;
});

// Update Model Header Display
function updateModelDisplay() {
    if (modelSelect.value === 'custom') {
        customModelWrapper.classList.remove('hidden');
        currentModelDisplay.textContent = customModelInput.value.trim() || 'Tùy chọn';
    } else {
        customModelWrapper.classList.add('hidden');
        const selectedOption = modelSelect.options[modelSelect.selectedIndex];
        currentModelDisplay.textContent = selectedOption.text.split(' (')[0];
    }
}

modelSelect.addEventListener('change', updateModelDisplay);
customModelInput.addEventListener('input', updateModelDisplay);

// Use suggestion chips
function useSuggestion(text) {
    userInput.value = text;
    userInput.dispatchEvent(new Event('input'));
    userInput.focus();
}

// Helper to scroll to bottom of chat
function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Create Message Element
function createMessageElement(role, content = '') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    // Add slide-up animation
    messageDiv.style.animation = 'slide-up 0.25s ease forwards';

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'avatar';
    
    const icon = role === 'user' ? 'user' : (role === 'system-error' ? 'alert-octagon' : 'bot');
    avatarDiv.innerHTML = `<i data-lucide="${icon}"></i>`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (role === 'assistant' && content === '') {
        // Create typing indicator for loading state
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        typingIndicator.innerHTML = '<span></span><span></span><span></span>';
        contentDiv.appendChild(typingIndicator);
    } else {
        contentDiv.innerHTML = formatMessageContent(content);
    }

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    
    messagesContainer.appendChild(messageDiv);
    lucide.createIcons();
    scrollToBottom();
    
    return messageDiv;
}

// Format message content with Marked & Highlight.js
function formatMessageContent(content) {
    if (!content) return '';
    try {
        const rawHtml = marked.parse(content);
        // Temporary container to parse and run highlighting on codeblocks
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = rawHtml;
        tempDiv.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
        return tempDiv.innerHTML;
    } catch (e) {
        console.error('Markdown rendering error:', e);
        // Fallback to plain text escaping
        const pre = document.createElement('pre');
        pre.textContent = content;
        return pre.outerHTML;
    }
}

// Clear Chat handler
clearChatBtn.addEventListener('click', () => {
    if (isGenerating) return;
    
    // Keep only the welcome message
    const welcome = messagesContainer.querySelector('.welcome-message');
    messagesContainer.innerHTML = '';
    if (welcome) {
        messagesContainer.appendChild(welcome);
    } else {
        // Re-create welcome if it was somehow deleted
        createWelcomeMessage();
    }
    
    chatHistory = [];
    localStorage.removeItem('gemma_chat_history');
});

function createWelcomeMessage() {
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'message assistant welcome-message';
    welcomeDiv.innerHTML = `
        <div class="avatar">
            <i data-lucide="bot"></i>
        </div>
        <div class="message-content">
            <h4>Xin chào! 👋</h4>
            <p>Tôi là trợ lý AI tích hợp mô hình Gemma 4 của Google qua OpenRouter. Tôi có thể giúp gì cho bạn hôm nay?</p>
            <div class="suggestion-chips">
                <button class="chip" onclick="useSuggestion('Giải thích thuật toán Quicksort bằng Python')">Giải thích Quicksort</button>
                <button class="chip" onclick="useSuggestion('Viết một email xin nghỉ ốm chuyên nghiệp bằng tiếng Anh')">Viết email xin nghỉ</button>
                <button class="chip" onclick="useSuggestion('Làm sao để tối ưu hóa hiệu năng API FastAPI?')">Tối ưu FastAPI API</button>
            </div>
        </div>
    `;
    messagesContainer.appendChild(welcomeDiv);
    lucide.createIcons();
}

// Handle submit form
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const text = userInput.value.trim();
    if (!text || isGenerating) return;
    
    isGenerating = true;
    userInput.value = '';
    userInput.style.height = 'auto';
    sendBtn.disabled = true;
    
    // 1. Add User Message
    createMessageElement('user', text);
    chatHistory.push({ role: 'user', content: text });
    
    // 2. Add Assistant Message with Typing Indicator
    const assistantMessageElement = createMessageElement('assistant');
    const contentDiv = assistantMessageElement.querySelector('.message-content');
    
    try {
        // 3. Determine the model identifier
        const chosenModel = modelSelect.value === 'custom' 
            ? (customModelInput.value.trim() || 'google/gemma-4-31b-it') 
            : modelSelect.value;

        // Make fetch request for streaming
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: chatHistory,
                model: chosenModel
            })
        });
        
        // Remove typing indicator
        contentDiv.innerHTML = '';
        
        if (!response.ok) {
            const errDetails = await response.text();
            throw new Error(errDetails || `Server HTTP ${response.status}`);
        }
        
        // 4. Handle Streaming Response
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let assistantText = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            assistantText += chunk;
            
            // Render markdown on the fly
            contentDiv.innerHTML = formatMessageContent(assistantText);
            scrollToBottom();
        }
        
        // Final decoding to flush any buffers
        const finalChunk = decoder.decode();
        if (finalChunk) {
            assistantText += finalChunk;
            contentDiv.innerHTML = formatMessageContent(assistantText);
        }
        
        // Save to chat history
        chatHistory.push({ role: 'model', content: assistantText });
        
    } catch (err) {
        console.error('Chat error:', err);
        
        // Handle UI update on error
        contentDiv.innerHTML = '';
        assistantMessageElement.className = 'message system-error';
        const avatarIcon = assistantMessageElement.querySelector('.avatar i');
        if (avatarIcon) {
            avatarIcon.setAttribute('data-lucide', 'alert-octagon');
            lucide.createIcons();
        }
        
        const errMessage = err.message || 'Lỗi không xác định khi kết nối với server.';
        contentDiv.innerHTML = `<p><strong>Lỗi hệ thống:</strong> ${errMessage}</p>`;
    } finally {
        isGenerating = false;
        sendBtn.disabled = false;
        userInput.focus();
        scrollToBottom();
    }
});

// Keydown listener for textarea (Ctrl+Enter or Enter without Shift to submit)
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.requestSubmit();
    }
});

// Initialize configuration check on load
checkConfig();
updateModelDisplay();
