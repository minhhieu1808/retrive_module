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

// --- Navigation Tab Switching Logic ---
const tabChatBtn = document.getElementById('tab-chat-btn');
const tabImageBtn = document.getElementById('tab-image-btn');
const chatArea = document.getElementById('chat-area');
const imageArea = document.getElementById('image-area');

if (tabChatBtn && tabImageBtn && chatArea && imageArea) {
    tabChatBtn.addEventListener('click', () => {
        tabChatBtn.classList.add('active');
        tabImageBtn.classList.remove('active');
        chatArea.classList.remove('hidden');
        imageArea.classList.add('hidden');
    });

    tabImageBtn.addEventListener('click', () => {
        tabImageBtn.classList.add('active');
        tabChatBtn.classList.remove('active');
        imageArea.classList.remove('hidden');
        chatArea.classList.add('hidden');
        lucide.createIcons();
    });
}

// --- Image Retrieval / Search Logic ---
const indexImagesBtn = document.getElementById('index-images-btn');
const indexingStatus = document.getElementById('indexing-status');
const indexingStatusText = document.getElementById('indexing-status-text');
const resultsCount = document.getElementById('results-count');
const imageResultsGrid = document.getElementById('image-results-grid');

// Tab selectors
const modeTextBtn = document.getElementById('mode-text-btn');
const modeImageBtn = document.getElementById('mode-image-btn');
const searchTextContainer = document.getElementById('search-text-container');
const searchImageContainer = document.getElementById('search-image-container');

// Text search
const imageTextSearchForm = document.getElementById('image-text-search-form');
const imageQueryTextInput = document.getElementById('image-query-text-input');

// Image upload/dropzone search
const imageDropzone = document.getElementById('image-dropzone');
const imageFileDropzoneInput = document.getElementById('image-file-dropzone-input');
const dropPreviewPane = document.getElementById('drop-preview-pane');
const dropPreviewImg = document.getElementById('drop-preview-img');
const dropPreviewName = document.getElementById('drop-preview-name');
const dropPreviewSize = document.getElementById('drop-preview-size');
const dropClearBtn = document.getElementById('drop-clear-btn');
const dropSearchBtn = document.getElementById('drop-search-btn');

// Stats Elements
const statsTotalImages = document.getElementById('stats-total-images');
const statsVectorDim = document.getElementById('stats-vector-dim');
const statsDbType = document.getElementById('stats-db-type');

// Lightbox Modal Elements
const lightboxModal = document.getElementById('lightbox-modal');
const lightboxBackdrop = document.getElementById('lightbox-backdrop');
const lightboxCloseBtn = document.getElementById('lightbox-close-btn');
const lightboxImg = document.getElementById('lightbox-img');
const lightboxTitle = document.getElementById('lightbox-title');
const lightboxBadgeMatch = document.getElementById('lightbox-badge-match');
const lightboxSimilarityBar = document.getElementById('lightbox-similarity-bar');
const lightboxSimilarityPercent = document.getElementById('lightbox-similarity-percent');
const lightboxDescription = document.getElementById('lightbox-description');
const lightboxPathInput = document.getElementById('lightbox-path-input');
const lightboxTimestamp = document.getElementById('lightbox-timestamp');
const copyPathBtn = document.getElementById('copy-path-btn');

// Current query states
let uploadedImageBase64 = null;
let currentSearchResults = [];

// Helper to format file sizes
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// 1. Fetch Database Statistics
async function fetchImageStats() {
    try {
        const response = await fetch('/api/images/stats');
        if (response.ok) {
            const stats = await response.json();
            if (stats.exists) {
                statsTotalImages.textContent = stats.points_count.toLocaleString();
                statsVectorDim.textContent = stats.vector_size ? stats.vector_size : 'Không xác định';
                statsDbType.textContent = 'Qdrant DB';
            } else {
                statsTotalImages.textContent = '0';
                statsVectorDim.textContent = 'Chưa tạo';
            }
        }
    } catch (err) {
        console.error('Error fetching database stats:', err);
    }
}

// Fetch stats when tab switches to image-search
if (tabImageBtn) {
    tabImageBtn.addEventListener('click', () => {
        fetchImageStats();
    });
}

// 2. Tab selection logic for Search Modes
if (modeTextBtn && modeImageBtn) {
    modeTextBtn.addEventListener('click', () => {
        modeTextBtn.classList.add('active');
        modeImageBtn.classList.remove('active');
        searchTextContainer.classList.remove('hidden');
        searchImageContainer.classList.add('hidden');
    });

    modeImageBtn.addEventListener('click', () => {
        modeImageBtn.classList.add('active');
        modeTextBtn.classList.remove('active');
        searchImageContainer.classList.remove('hidden');
        searchTextContainer.classList.add('hidden');
        lucide.createIcons();
    });
}

// Helper chip functions
window.useImageSuggestion = function(text) {
    if (imageQueryTextInput) {
        imageQueryTextInput.value = text;
        if (imageTextSearchForm) {
            // Trigger submit event
            imageTextSearchForm.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    }
};

// 3. Dropzone & File Upload Logic
if (imageDropzone && imageFileDropzoneInput) {
    // Click dropzone to trigger browser file upload
    imageDropzone.addEventListener('click', () => {
        imageFileDropzoneInput.click();
    });

    // Handle file drag events
    ['dragenter', 'dragover'].forEach(eventName => {
        imageDropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            imageDropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        imageDropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            imageDropzone.classList.remove('dragover');
        }, false);
    });

    // Drop file handler
    imageDropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleUploadedFile(files[0]);
        }
    });

    // Selected file handler
    imageFileDropzoneInput.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            handleUploadedFile(files[0]);
        }
    });
}

// Process and display upload preview
function handleUploadedFile(file) {
    if (!file.type.startsWith('image/')) {
        alert('Vui lòng chỉ tải lên tệp tin định dạng hình ảnh.');
        return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
        uploadedImageBase64 = event.target.result;
        dropPreviewImg.src = uploadedImageBase64;
        dropPreviewName.textContent = file.name;
        dropPreviewSize.textContent = formatBytes(file.size);
        
        imageDropzone.classList.add('hidden');
        dropPreviewPane.classList.remove('hidden');
    };
    reader.readAsDataURL(file);
}

// Clear upload file
if (dropClearBtn) {
    dropClearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        uploadedImageBase64 = null;
        imageFileDropzoneInput.value = '';
        dropPreviewPane.classList.add('hidden');
        imageDropzone.classList.remove('hidden');
        dropPreviewImg.src = '';
    });
}

// 4. Submit Search Handlers
// Text to Image Search Form
if (imageTextSearchForm) {
    imageTextSearchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = imageQueryTextInput.value.trim();
        if (!query) return;
        executeImageSearch(query, null);
    });
}

// Image to Image Search trigger
if (dropSearchBtn) {
    dropSearchBtn.addEventListener('click', () => {
        if (!uploadedImageBase64) return;
        executeImageSearch(null, uploadedImageBase64);
    });
}

// Core execution method
async function executeImageSearch(queryText, imageBase64) {
    resultsCount.textContent = 'Đang tìm kiếm...';
    imageResultsGrid.innerHTML = `
        <div class="grid-placeholder">
            <div class="spinner" style="width: 32px; height: 32px; margin-bottom: 16px;"></div>
            <p>Đang tìm kiếm hình ảnh phù hợp trong Qdrant Vector DB...</p>
        </div>
    `;

    try {
        let response;
        if (imageBase64) {
            response = await fetch('/api/images/search-by-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageBase64, limit: 6 })
            });
        } else {
            response = await fetch(`/api/images/search?query=${encodeURIComponent(queryText)}`);
        }

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(errText || `HTTP ${response.status}`);
        }

        const data = await response.json();
        currentSearchResults = data.results || [];
        
        resultsCount.textContent = `Tìm thấy ${currentSearchResults.length} hình ảnh`;

        if (currentSearchResults.length === 0) {
            imageResultsGrid.innerHTML = `
                <div class="grid-placeholder">
                    <i data-lucide="image-off"></i>
                    <p>Không tìm thấy hình ảnh phù hợp. Vui lòng thử từ khóa mô tả hoặc hình ảnh truy vấn khác.</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        // Render card grids
        imageResultsGrid.innerHTML = currentSearchResults.map((img, idx) => `
            <div class="image-card" style="animation: slide-up 0.3s ease forwards;">
                <div class="image-card-img-wrapper" onclick="openLightboxByIndex(${idx})">
                    <img src="/image/${img.file_name}" alt="${img.file_name}" onerror="this.src='/static/placeholder.svg'; this.onerror=null;">
                    <span class="similarity-badge">
                        <i data-lucide="zap"></i> Match ${img.percentage}%
                    </span>
                </div>
                <div class="image-card-info">
                    <div class="image-card-title" title="${img.file_name}" onclick="openLightboxByIndex(${idx})">${img.file_name}</div>
                    
                    <div class="similarity-bar-container">
                        <div class="similarity-bar-label">
                            <span>Độ tương đồng</span>
                            <span>${img.percentage}%</span>
                        </div>
                        <div class="similarity-bar-bg">
                            <div class="similarity-bar-fill" id="similarity-bar-fill-${idx}" style="width: 0%;"></div>
                        </div>
                    </div>
                    
                    <div class="image-card-description" title="${img.description || ''}">
                        ${img.description || 'Không có mô tả chi tiết từ AI.'}
                    </div>
                    
                    <button class="image-card-btn-view" onclick="openLightboxByIndex(${idx})">
                        <i data-lucide="info"></i> Xem chi tiết
                    </button>
                    
                    <div class="image-card-meta">
                        <i data-lucide="folder"></i>
                        <span title="${img.file_path}">${img.file_name}</span>
                    </div>
                </div>
            </div>
        `).join('');

        // Progress bar fill animation
        setTimeout(() => {
            currentSearchResults.forEach((img, idx) => {
                const fill = document.getElementById(`similarity-bar-fill-${idx}`);
                if (fill) fill.style.width = `${img.percentage}%`;
            });
        }, 50);

        lucide.createIcons();

    } catch (err) {
        console.error('Image search error:', err);
        resultsCount.textContent = 'Lỗi truy vấn';
        imageResultsGrid.innerHTML = `
            <div class="grid-placeholder">
                <i data-lucide="alert-circle" style="color: var(--error-color);"></i>
                <p style="color: var(--error-color);"><strong>Lỗi hệ thống:</strong> ${err.message || 'Không thể kết nối với server.'}</p>
            </div>
        `;
        lucide.createIcons();
    }
}

// 5. Index directory handler
if (indexImagesBtn) {
    indexImagesBtn.addEventListener('click', async () => {
        indexImagesBtn.disabled = true;
        indexingStatus.classList.remove('hidden');
        indexingStatusText.textContent = 'Đang quét thư mục và sinh vector embeddings (Qwen-VL) lưu vào Qdrant...';

        try {
            const response = await fetch('/api/images/index', { method: 'POST' });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || `HTTP ${response.status}`);
            }

            const data = await response.json();
            const success = data.success_count || 0;
            const total = data.total_processed || 0;
            const fail = data.fail_count || 0;

            indexingStatusText.textContent = `Lập chỉ mục hoàn tất! Đã xử lý ${total} ảnh (Thành công: ${success}, Thất bại: ${fail})`;
            
            // Refresh DB Stats
            fetchImageStats();

            // Render confirmation
            if (success > 0) {
                imageResultsGrid.innerHTML = `
                    <div class="grid-placeholder">
                        <i data-lucide="sparkles" style="color: var(--success-color);"></i>
                        <p>Qdrant Vector Database đã được cập nhật với ${success} hình ảnh mới. Hãy bắt đầu tìm kiếm!</p>
                    </div>
                `;
                lucide.createIcons();
            }
        } catch (err) {
            console.error('Indexing error:', err);
            indexingStatusText.textContent = `Lỗi lập chỉ mục: ${err.message || 'Không thể kết nối với server.'}`;
        } finally {
            setTimeout(() => {
                indexingStatus.classList.add('hidden');
                indexImagesBtn.disabled = false;
            }, 5000);
        }
    });
}

// 6. Lightbox Modal Event Handlers
window.openLightboxByIndex = function(index) {
    const img = currentSearchResults[index];
    if (!img || !lightboxModal) return;

    lightboxImg.src = `/image/${img.file_name}`;
    lightboxTitle.textContent = img.file_name;
    lightboxBadgeMatch.textContent = `Match ${img.percentage}%`;
    lightboxSimilarityPercent.textContent = `${img.percentage}%`;
    lightboxSimilarityBar.style.width = `0%`; // start animation from 0
    lightboxDescription.textContent = img.description || 'Không có mô tả chi tiết từ AI cho hình ảnh này.';
    lightboxPathInput.value = img.file_path || '';
    
    // Format timestamp nicely
    if (img.timestamp) {
        try {
            const date = new Date(img.timestamp);
            lightboxTimestamp.textContent = date.toLocaleString('vi-VN');
        } catch (e) {
            lightboxTimestamp.textContent = img.timestamp;
        }
    } else {
        lightboxTimestamp.textContent = 'N/A';
    }

    lightboxModal.classList.remove('hidden');
    lucide.createIcons();
    
    // Animate similarity bar inside lightbox
    setTimeout(() => {
        lightboxSimilarityBar.style.width = `${img.percentage}%`;
    }, 100);
};

function closeLightbox() {
    if (lightboxModal) {
        lightboxModal.classList.add('hidden');
    }
}

if (lightboxCloseBtn) {
    lightboxCloseBtn.addEventListener('click', closeLightbox);
}

if (lightboxBackdrop) {
    lightboxBackdrop.addEventListener('click', closeLightbox);
}

// Keyboard ESC to close lightbox
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeLightbox();
    }
});

// Copy path logic
if (copyPathBtn && lightboxPathInput) {
    copyPathBtn.addEventListener('click', () => {
        lightboxPathInput.select();
        lightboxPathInput.setSelectionRange(0, 99999); // For mobile devices
        
        try {
            navigator.clipboard.writeText(lightboxPathInput.value);
            const originalHTML = copyPathBtn.innerHTML;
            copyPathBtn.innerHTML = '<i data-lucide="check"></i> Đã chép';
            copyPathBtn.classList.remove('btn-secondary');
            copyPathBtn.classList.add('btn-primary');
            lucide.createIcons();
            
            setTimeout(() => {
                copyPathBtn.innerHTML = originalHTML;
                copyPathBtn.classList.remove('btn-primary');
                copyPathBtn.classList.add('btn-secondary');
                lucide.createIcons();
            }, 2000);
        } catch (err) {
            console.error('Copy path failed:', err);
            alert('Không thể tự động sao chép. Vui lòng nhấn Ctrl+C để sao chép thủ công.');
        }
    });
}
