document.addEventListener('DOMContentLoaded', function () {
    const chatForm = document.getElementById('chat-form');
    const questionInput = document.getElementById('questionInput');
    const chatMessages = document.getElementById('chatMessages');
    const charCount = document.getElementById('charCount');

    // Clean up the initial message whitespace
    const initialMessage = document.querySelector('.message.assistant .message-content');
    if (initialMessage) {
        initialMessage.textContent = initialMessage.textContent.trim().replace(/\s+/g, ' ');
    }

    // Rate limiting variables
    const rateLimits = {
        lastRequestTime: 0,
        requestsInLastMinute: 0,
        requestsInLastDay: 0,
        shortCooldown: 5000, // 5 seconds between requests
        minuteLimit: 5, // 5 requests per minute
        dayLimit: 20, // 20 requests per day
        resetTime: Date.now() + 86400000 // 24 hours from now
    };

    // Create toast container
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);

    // Function to show toast notification
    function showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        toastContainer.appendChild(toast);

        // Animate in
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        // Remove after duration
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toastContainer.removeChild(toast);
            }, 300);
        }, duration);
    }

    // Check if rate limited
    function isRateLimited() {
        const now = Date.now();

        // Reset daily counter if needed
        if (now > rateLimits.resetTime) {
            rateLimits.requestsInLastDay = 0;
            rateLimits.resetTime = now + 86400000; // 24 hours from now
        }

        // Check if too soon after last request
        if (now - rateLimits.lastRequestTime < rateLimits.shortCooldown) {
            showToast('Please wait a moment before sending another message.', 'warning');
            return true;
        }

        // Check minute limit
        if (rateLimits.requestsInLastMinute >= rateLimits.minuteLimit) {
            const timeUntilReset = Math.ceil((rateLimits.lastRequestTime + 60000 - now) / 1000);
            showToast(`Rate limit reached. Please wait ${timeUntilReset} seconds.`, 'error', 5000);
            return true;
        }

        // Check daily limit
        if (rateLimits.requestsInLastDay >= rateLimits.dayLimit) {
            showToast('Daily message limit reached. Please try again tomorrow.', 'error', 5000);
            return true;
        }

        return false;
    }

    // Update rate limit counters
    function updateRateLimits() {
        const now = Date.now();

        // Update request time
        rateLimits.lastRequestTime = now;

        // Update minute counter
        rateLimits.requestsInLastMinute++;
        setTimeout(() => {
            rateLimits.requestsInLastMinute--;
        }, 60000); // Decrease after 1 minute

        // Update daily counter
        rateLimits.requestsInLastDay++;
    }

    // Character counter with color changes
    questionInput.addEventListener('input', function () {
        const count = this.value.length;
        const maxChars = 200;
        charCount.textContent = `${count}/${maxChars}`;

        // Change color when approaching limit
        if (count > 180) {
            charCount.classList.add('near-limit');
            charCount.classList.remove('over-limit');
        } else if (count >= maxChars) {
            charCount.classList.add('over-limit');
            charCount.classList.remove('near-limit');
        } else {
            charCount.classList.remove('near-limit', 'over-limit');
        }
    });

    // Add these at the top of your script, after the DOMContentLoaded event starts
    let isProcessing = false;
    let processingTimeout = null;

    // Update the message queue object to properly handle references
    const messageQueue = {
        messages: [],
        pendingResponse: false,

        // Add a message to the queue
        add: function (type, content, isLoading = false) {
            const id = 'msg-' + Date.now();
            const message = { id, type, content, isLoading, references: [] };
            this.messages.push(message);
            this.render();
            return id;
        },

        // Remove a message by ID
        remove: function (id) {
            this.messages = this.messages.filter(msg => msg.id !== id);
            this.render();
        },

        // Replace a loading message with actual content
        replaceLoading: function (content) {
            const loadingIndex = this.messages.findIndex(msg => msg.isLoading);
            if (loadingIndex !== -1) {
                this.messages[loadingIndex].content = content;
                this.messages[loadingIndex].isLoading = false;
                this.render();
                return this.messages[loadingIndex].id;
            }
            return null;
        },

        // Render all messages in the queue
        render: function () {
            // First, make sure we have the right number of message elements
            while (chatMessages.children.length < this.messages.length) {
                // Add new message divs if needed
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message';

                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';

                messageDiv.appendChild(contentDiv);
                chatMessages.appendChild(messageDiv);
            }

            // Remove extra message divs if needed
            while (chatMessages.children.length > this.messages.length) {
                chatMessages.removeChild(chatMessages.lastChild);
            }

            // Now update each message div with the correct content
            for (let i = 0; i < this.messages.length; i++) {
                const msg = this.messages[i];
                const messageDiv = chatMessages.children[i];

                // Update ID and class
                messageDiv.id = msg.id;
                messageDiv.className = `message ${msg.type}`;

                // Update content
                const contentDiv = messageDiv.querySelector('.message-content');
                contentDiv.innerHTML = msg.content.replace(/\n/g, '<br>');

                // Add references if they exist
                if (msg.references && msg.references.length > 0) {
                    // Check if references element already exists
                    let refsElement = contentDiv.querySelector('.references');
                    if (!refsElement) {
                        refsElement = document.createElement('div');
                        refsElement.className = 'references';
                        contentDiv.appendChild(refsElement);
                    }

                    const refsHtml = msg.references.map(ref => {
                        // Convert reference title to a section link
                        const sectionId = ref.title.toLowerCase();
                        return `<a href="https://sohae-kim.github.io/#${sectionId}" target="_blank">${ref.title}</a>`;
                    }).join(', ');

                    refsElement.innerHTML = `Learn more: ${refsHtml}`;
                } else {
                    // Remove references element if it exists but shouldn't
                    const existingRefs = contentDiv.querySelector('.references');
                    if (existingRefs) {
                        contentDiv.removeChild(existingRefs);
                    }
                }
            }

            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        },

        // Add references to a message
        addReferences: function (messageId, references) {
            const messageIndex = this.messages.findIndex(msg => msg.id === messageId);
            if (messageIndex !== -1) {
                // Store references in the message object
                this.messages[messageIndex].references = references;
                // Re-render to update the UI
                this.render();
            }
        }
    };

    // Initialize the queue with the intro message
    function initializeChat() {
        // Get the initial message from the DOM
        const initialMessageElement = document.querySelector('.message.assistant');
        if (initialMessageElement) {
            const contentElement = initialMessageElement.querySelector('.message-content');
            if (contentElement) {
                const initialText = contentElement.textContent.trim().replace(/\s+/g, ' ');

                // Clear the chat container
                chatMessages.innerHTML = '';

                // Add the initial message to our queue
                messageQueue.add('assistant', initialText);
            }
        }
    }

    // Call initialization
    initializeChat();

    // Replace your chatForm event listener with this one
    chatForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const question = questionInput.value.trim();
        if (!question) return;

        // Check rate limiting before proceeding
        if (isRateLimited()) {
            return;
        }

        // Prevent multiple submissions while processing
        if (isProcessing) {
            showToast('Please wait for the previous message to complete', 'warning');
            return;
        }

        // Set processing flag
        isProcessing = true;

        // Add user message to queue
        messageQueue.add('user', question);

        // Clear input
        questionInput.value = '';
        charCount.textContent = '0/200';
        charCount.classList.remove('near-limit', 'over-limit');

        // Add loading indicator to queue
        messageQueue.add('assistant', 'Thinking...', true);

        // Update rate limits
        updateRateLimits();

        try {
            // Call API
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question }),
            });

            const data = await response.json();

            if (response.ok) {
                // Replace loading message with actual response
                const messageId = messageQueue.replaceLoading(data.answer);

                // Add references if available
                if (data.references && data.references.length > 0) {
                    messageQueue.addReferences(messageId, data.references);
                }
            } else {
                // Handle rate limiting response from server
                if (data.detail && data.detail.includes('rate limit')) {
                    messageQueue.replaceLoading('');  // Remove the loading message
                    showToast(data.detail, 'error', 5000);
                } else {
                    messageQueue.replaceLoading(data.error || 'An error occurred. Please try again.');
                }
            }
        } catch (error) {
            // Replace loading with error message
            messageQueue.replaceLoading('Network error. Please check your connection and try again.');
            console.error('Error:', error);
        } finally {
            // Reset processing flag
            isProcessing = false;
        }
    });

    // Replace your addMessage function with this one that uses the queue
    function addMessage(type, content, isLoading = false) {
        return messageQueue.add(type, content, isLoading);
    }
}); 