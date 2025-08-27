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

    // --- Event Listeners ---
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        addMessageToUI(message, 'user');
        messageInput.value = '';

        if (!agentIsActive) {
            startAgent(message);
        } else {
            // Send subsequent messages to the running agent
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(message);
            }
        }
    });

    controlButton.addEventListener('click', () => {
        if (agentIsActive && socket) {
            socket.send('stop'); // Graceful stop
            socket.close();
            addMessageToUI('تم إيقاف الوكيل. أُعيدت السيطرة لك.', 'agent status');
            setAgentState(false);
        }
    });

    resumeButton.addEventListener('click', () => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send('resume');
            pauseOverlay.classList.add('hidden');
        }
    });

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
            controlButton.textContent = 'تم إيقاف الوكيل';
            controlButton.disabled = true;
        }
    }

    // --- WebSocket Logic ---
    function startAgent(initialTask) {
        socket = new WebSocket('ws://localhost:8000/ws/execute_task');
        setAgentState(true);

        socket.onopen = () => {
            addMessageToUI('تم الاتصال بالوكيل...', 'agent status');
            socket.send(initialTask);
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
            addMessageToUI('فشل الاتصال بالوكيل.', 'agent error');
            setAgentState(false);
        };

        socket.onclose = () => {
            if (agentIsActive) { // If it was closed while active
                addMessageToUI('انقطع الاتصال بالوكيل.', 'agent status');
            }
            setAgentState(false);
        };
    }

    // --- Utility ---
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
