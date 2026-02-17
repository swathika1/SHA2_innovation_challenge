/* MeriLion AI Chatbot Widget */
(function() {
    var chatConversation = [];
    var chatOpen = false;
    // chatPatientId is set via inline script before this file loads
    var chatPatientId = window.CHAT_PATIENT_ID || null;

    window.toggleChat = function() {
        var win = document.getElementById('chat-window');
        var fab = document.getElementById('chat-fab-icon');
        chatOpen = !chatOpen;
        win.style.display = chatOpen ? 'flex' : 'none';
        fab.textContent = chatOpen ? '\u2715' : '\uD83D\uDCAC';
    };

    window.sendQuickMessage = function(msg) {
        document.getElementById('chat-input').value = msg;
        sendMessage();
    };

    window.sendMessage = function() {
        var input = document.getElementById('chat-input');
        var msg = input.value.trim();
        if (!msg) return;

        appendMessage('user', msg);
        input.value = '';
        chatConversation.push({role: 'user', content: msg});

        var typingEl = showTyping();
        var sendBtn = document.getElementById('chat-send-btn');
        sendBtn.disabled = true;

        var body = {
            message: msg,
            conversation_history: chatConversation.slice(0, -1)
        };

        // Use override if caregiver selected a different patient
        var pid = window._chatPatientIdOverride || chatPatientId;
        if (pid) {
            body.patient_id = pid;
        }

        fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            removeTyping(typingEl);
            sendBtn.disabled = false;

            if (data.error) {
                appendMessage('bot', 'Sorry, something went wrong: ' + data.error);
                return;
            }

            if (data.language) {
                var langNames = {en: 'EN', zh: '\u4E2D\u6587', ms: 'BM', ta: '\u0BA4\u0BAE\u0BBF\u0BB4\u0BCD'};
                document.getElementById('chat-lang-badge').textContent = langNames[data.language] || data.language.toUpperCase();
            }

            if (data.referred) {
                document.getElementById('chat-risk-alert').style.display = 'block';
            }

            var riskNote = '';
            if (data.risk_score >= 4 && data.risk_score < 7) {
                riskNote = '\n\n\u26A1 Moderate concern detected \u2014 consider mentioning this to your doctor.';
            }

            appendMessage('bot', data.response + riskNote);
            chatConversation.push({role: 'assistant', content: data.response});
        })
        .catch(function(err) {
            removeTyping(typingEl);
            sendBtn.disabled = false;
            appendMessage('bot', 'Sorry, I could not connect to the server. Please try again.');
            console.error('Chat error:', err);
        });
    };

    function appendMessage(role, text) {
        var container = document.getElementById('chat-messages');
        var msgDiv = document.createElement('div');
        msgDiv.className = 'chat-msg ' + role;

        var bubble = document.createElement('div');
        bubble.className = 'chat-bubble ' + (role === 'user' ? 'user-bubble' : 'bot-bubble');
        bubble.innerHTML = formatText(text);

        msgDiv.appendChild(bubble);
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
    }

    function formatText(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }

    function showTyping() {
        var container = document.getElementById('chat-messages');
        var typingDiv = document.createElement('div');
        typingDiv.className = 'chat-msg bot';
        typingDiv.innerHTML = '<div class="chat-bubble bot-bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
        container.appendChild(typingDiv);
        container.scrollTop = container.scrollHeight;
        return typingDiv;
    }

    function removeTyping(el) {
        if (el && el.parentNode) el.parentNode.removeChild(el);
    }
})();
