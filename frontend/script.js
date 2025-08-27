document.addEventListener('DOMContentLoaded', () => {
    const taskInput = document.getElementById('task-input');
    const startButton = document.getElementById('start-button');
    const logContainer = document.getElementById('log');
    let socket = null;

    startButton.addEventListener('click', () => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            // If socket is open, the button is for stopping
            socket.send('stop');
            updateUIForStop();
        } else {
            // Otherwise, the button is for starting
            startAgent();
        }
    });

    function startAgent() {
        const task = taskInput.value;
        if (!task) {
            alert('Please enter a task for the agent.');
            return;
        }

        // Connect to the WebSocket server
        socket = new WebSocket('ws://localhost:8000/ws/execute_task');

        updateUIForStart();

        socket.onopen = () => {
            logContainer.innerHTML = '<p>Connection established. Sending task to agent...</p>';
            socket.send(task);
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            renderLogEntry(data);
        };

        socket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            renderLogEntry({ type: 'error', message: 'WebSocket connection failed.' });
            updateUIForStop();
        };

        socket.onclose = () => {
            console.log('WebSocket connection closed.');
            if (startButton.textContent.includes('Stop')) {
                 renderLogEntry({ type: 'status', message: 'Connection closed.' });
            }
            updateUIForStop();
        };
    }

    function updateUIForStart() {
        logContainer.innerHTML = '<p>Attempting to connect to agent...</p>';
        startButton.textContent = 'Stop Agent';
        startButton.style.backgroundColor = '#e53e3e'; // Red for stop
        taskInput.disabled = true;
    }

    function updateUIForStop() {
        if (socket) {
            socket.close();
            socket = null;
        }
        startButton.textContent = 'Start Agent';
        startButton.style.backgroundColor = '#4a90e2'; // Blue for start
        taskInput.disabled = false;
    }

    let isFirstMessage = true;
    function renderLogEntry(entry) {
        if (isFirstMessage) {
            logContainer.innerHTML = ''; // Clear the initial status message
            isFirstMessage = false;
        }

        const entryDiv = document.createElement('div');
        entryDiv.className = 'log-entry';

        if (entry.thought) {
            entryDiv.classList.add('log-thought');
            entryDiv.innerHTML = `<strong>Thought:</strong> ${escapeHtml(entry.thought)}`;
        } else if (entry.action) {
            entryDiv.classList.add('log-action');
            let params = JSON.stringify(entry.params || {});
            entryDiv.innerHTML = `<strong>Action:</strong> ${entry.action}(${params})`;
        } else if (entry.type === 'action_result') {
             entryDiv.classList.add('log-action-result');
             entryDiv.innerHTML = `<strong>Result from ${entry.tool}:</strong><pre>${escapeHtml(entry.output)}</pre>`;
        } else if (entry.type === 'error') {
            entryDiv.classList.add('log-error');
            entryDiv.innerHTML = `<strong>Error:</strong> ${escapeHtml(entry.message)}`;
        } else if (entry.type === 'status') {
            entryDiv.classList.add('log-status');
            entryDiv.innerHTML = `<strong>Status:</strong> ${escapeHtml(entry.message)}`;
        } else {
            // Fallback for unexpected message format
            entryDiv.classList.add('log-status');
            entryDiv.innerHTML = `<strong>System:</strong> ${escapeHtml(JSON.stringify(entry))}`;
        }

        logContainer.appendChild(entryDiv);
        logContainer.scrollTop = logContainer.scrollHeight;
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
