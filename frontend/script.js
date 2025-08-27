document.addEventListener('DOMContentLoaded', () => {
    const messageList = document.getElementById('message-list');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const controlButton = document.getElementById('control-button');
    const pauseOverlay = document.getElementById('pause-overlay');
    const pauseMessage = document.getElementById('pause-message');
    const resumeButton = document.getElementById('resume-button');

    let socket = null;
    let agentIsActive = false;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    const baseReconnectDelay = 1000; // 1 second

    // --- Event Listeners ---
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        addMessageToUI(message, 'user');
        messageInput.value = '';

        if (!agentIsActive && (!socket || socket.readyState === WebSocket.CLOSED)) {
            // If agent isn't active and socket is not open, start a new session
            connect(message);
        } else if (socket && socket.readyState === WebSocket.OPEN) {
            // If socket is open, just send the message
            socket.send(message);
        }
    });

    controlButton.addEventListener('click', () => {
        if (agentIsActive && socket) {
            // User-initiated stop, don't try to reconnect
            reconnectAttempts = maxReconnectAttempts + 1; // Prevent reconnection
            socket.send('stop');
            socket.close();
        }
    });

    resumeButton.addEventListener('click', () => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send('resume');
            pauseOverlay.classList.add('hidden');
        }
    });

    // --- WebSocket Connection Logic ---
    function connect(initialTask) {
        const uri = "ws://localhost:8000/ws/execute_task";
        socket = new WebSocket(uri);
        setAgentState(true);
        addMessageToUI('جاري الاتصال بالوكيل...', 'agent status');

        socket.onopen = () => {
            addMessageToUI('تم الاتصال بنجاح.', 'agent status');
            reconnectAttempts = 0; // Reset on successful connection
            if (initialTask) {
                socket.send(initialTask);
            }
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'pause') {
                handlePause(data);
            } else {
                addMessageToUI(null, 'agent', data);
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            addMessageToUI('حدث خطأ في الاتصال.', 'agent error');
            // The onclose event will handle the reconnect logic
        };

        socket.onclose = (event) => {
            setAgentState(false);
            if (reconnectAttempts > maxReconnectAttempts) {
                addMessageToUI('تم إنهاء الاتصال. أعد تحميل الصفحة للمحاولة مرة أخرى.', 'agent status');
                return;
            }
            if (event.wasClean) {
                addMessageToUI('انقطع الاتصال بالوكيل.', 'agent status');
            } else {
                // Connection died, try to reconnect
                const delay = Math.pow(2, reconnectAttempts) * baseReconnectDelay;
                reconnectAttempts++;
                addMessageToUI(`انقطع الاتصال. جاري محاولة إعادة الاتصال بعد ${delay / 1000} ثانية... (محاولة ${reconnectAttempts}/${maxReconnectAttempts})`, 'agent error');
                setTimeout(() => {
                    // We don't have an initial task for reconnect, the user will have to send a new message
                    connect(null);
                }, delay);
            }
        };
    }

    // --- UI Functions ---
    function addMessageToUI(content, type, data = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', type);
        let htmlContent = '';

        if (type === 'user') {
            htmlContent = escapeHtml(content);
        } else if (data.thought) {
            messageDiv.classList.add('thought');
            htmlContent = `<strong>فكرة:</strong> <em>${escapeHtml(data.thought)}</em>`;
        } else if (data.action) {
            messageDiv.classList.add('action');
            let params = JSON.stringify(data.params || {});
            htmlContent = `<strong>إجراء:</strong> ${data.action}(${params})`;
        } else if (data.type === 'action_result') {
            messageDiv.classList.add('action');
            htmlContent = `<strong>نتيجة ${data.tool}:</strong><pre>${escapeHtml(data.output)}</pre>`;
        } else if (data.type === 'error') {
            messageDiv.classList.add('error');
            htmlContent = `<strong>خطأ:</strong> ${escapeHtml(data.message)}`;
        } else if (data.type === 'status' || type === 'agent status') {
             messageDiv.classList.add('status');
             htmlContent = `<strong>النظام:</strong> ${escapeHtml(content || data.message)}`;
        }

        messageDiv.innerHTML = htmlContent;
        messageList.appendChild(messageDiv);
        messageList.scrollTop = messageList.scrollHeight;
    }

    function handlePause(data) {
        pauseMessage.textContent = data.message || "توقف الوكيل مؤقتًا لتدخلك.";
        pauseOverlay.classList.remove('hidden');
    }

    function setAgentState(isActive) {
        agentIsActive = isActive;
        if (isActive) {
            controlButton.textContent = 'استلام التحكم';
            controlButton.disabled = false;
        } else {
            controlButton.textContent = 'الوكيل متوقف';
            controlButton.disabled = true;
        }
    }

    function escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') {
            unsafe = JSON.stringify(unsafe);
        }
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
});
