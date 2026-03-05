/* MeriLion AI Chatbot Widget */
(function() {
    var STORAGE_KEY = 'rehab_chat_history';
    var STORAGE_HTML_KEY = 'rehab_chat_html';
    var STORAGE_LANG_KEY = 'rehab_chat_lang';
    var STORAGE_OPEN_KEY = 'rehab_chat_open';
    var STORAGE_LISTEN_KEY = 'rehab_chat_listen';
    var STORAGE_TTS_LANG_KEY = 'rehab_chat_tts_lang';

    // Multilingual UI strings
    var UI_STRINGS = {
        en: {
            welcome: "Hello! I'm your AI health assistant. I can help you with:",
            item1: "Understanding your rehab exercises",
            item2: "Exercise modifications for pain",
            item3: "General health guidance",
            langNote: "I support English, 中文, Bahasa Melayu, and தமிழ் — you can speak or type!",
            chip1: "My Progress",
            chip1_msg: "How are my exercises going?",
            chip2: "Report Pain",
            chip2_msg: "I have pain during exercise",
            chip3: "Modify Plan",
            chip3_msg: "Can you modify my exercises?",
            placeholder: "Type or speak your message...",
            errorConnect: "Sorry, I could not connect to the server. Please try again.",
            errorPrefix: "Sorry, something went wrong: ",
            moderateRisk: "\n\n⚡ Moderate concern detected — consider mentioning this to your doctor.",
            micNoAudio: "🎤 I couldn't catch that — could you please repeat or type your message?",
            micError: "🎤 Sorry, the voice transcription failed. Please try again or type your message."
        },
        zh: {
            welcome: "你好！我是你的AI健康助手。我可以帮助你：",
            item1: "了解你的康复练习",
            item2: "疼痛时的运动调整",
            item3: "一般健康指导",
            langNote: "我支持 English, 中文, Bahasa Melayu, 和 தமிழ் — 你可以说话或打字！",
            chip1: "我的进度",
            chip1_msg: "我的康复进度如何？",
            chip2: "报告疼痛",
            chip2_msg: "我运动时感到疼痛",
            chip3: "调整计划",
            chip3_msg: "可以调整我的运动计划吗？",
            placeholder: "输入或说出您的消息...",
            errorConnect: "抱歉，无法连接到服务器。请重试。",
            errorPrefix: "抱歉，出了点问题：",
            moderateRisk: "\n\n⚡ 检测到中度风险——建议咨询您的医生。",
            micNoAudio: "🎤 没有听清楚，请再说一遍或输入您的消息。",
            micError: "🎤 语音识别失败，请再试一次或输入您的消息。"
        },
        ms: {
            welcome: "Hai! Saya pembantu kesihatan AI anda. Saya boleh membantu anda dengan:",
            item1: "Memahami latihan pemulihan anda",
            item2: "Pengubahsuaian senaman untuk kesakitan",
            item3: "Panduan kesihatan umum",
            langNote: "Saya menyokong English, 中文, Bahasa Melayu, dan தமிழ் — anda boleh bercakap atau menaip!",
            chip1: "Kemajuan Saya",
            chip1_msg: "Bagaimana kemajuan latihan saya?",
            chip2: "Lapor Sakit",
            chip2_msg: "Saya rasa sakit semasa bersenam",
            chip3: "Ubah Pelan",
            chip3_msg: "Boleh ubah pelan senaman saya?",
            placeholder: "Taip atau sebut mesej anda...",
            errorConnect: "Maaf, tidak dapat menyambung ke pelayan. Sila cuba lagi.",
            errorPrefix: "Maaf, ada masalah: ",
            moderateRisk: "\n\n⚡ Kebimbangan sederhana dikesan — pertimbangkan untuk memberitahu doktor anda.",
            micNoAudio: "🎤 Saya tidak dapat mendengar dengan jelas — sila ulang atau taip mesej anda.",
            micError: "🎤 Transkripsi suara gagal. Sila cuba lagi atau taip mesej anda."
        },
        ta: {
            welcome: "வணக்கம்! நான் உங்கள் AI சுகாதார உதவியாளர். நான் உங்களுக்கு உதவ முடியும்:",
            item1: "உங்கள் மறுவாழ்வு பயிற்சிகளை புரிந்துகொள்ளுதல்",
            item2: "வலிக்கான பயிற்சி மாற்றங்கள்",
            item3: "பொது சுகாதார வழிகாட்டுதல்",
            langNote: "English, 中文, Bahasa Melayu, மற்றும் தமிழ் ஆகியவற்றை ஆதரிக்கிறேன் — பேசலாம் அல்லது தட்டச்சு செய்யலாம்!",
            chip1: "என் முன்னேற்றம்",
            chip1_msg: "என் பயிற்சி எப்படி போகிறது?",
            chip2: "வலி தெரிவி",
            chip2_msg: "பயிற்சியின் போது வலி உள்ளது",
            chip3: "திட்டம் மாற்று",
            chip3_msg: "என் பயிற்சித் திட்டத்தை மாற்ற முடியுமா?",
            placeholder: "உங்கள் செய்தியை தட்டச்சு செய்யுங்கள் அல்லது பேசுங்கள்...",
            errorConnect: "மன்னிக்கவும், சேவையகத்துடன் இணைக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.",
            errorPrefix: "மன்னிக்கவும், ஏதோ தவறு: ",
            moderateRisk: "\n\n⚡ மிதமான அக்கறை கண்டறியப்பட்டது — உங்கள் மருத்துவரிடம் தெரிவிக்கவும்.",
            micNoAudio: "🎤 சரியாக கேட்கவில்லை — மீண்டும் பேசுங்கள் அல்லது தட்டச்சு செய்யுங்கள்.",
            micError: "🎤 குரல் எழுத்தாக்கம் தோல்வியடைந்தது. மீண்டும் முயற்சிக்கவும் அல்லது தட்டச்சு செய்யுங்கள்."
        }
    };

    var chatConversation = [];
    var chatOpen = false;
    var currentLang = 'en';
    var chatPatientId = window.CHAT_PATIENT_ID || null;

    // ---- Speech state ----
    var listenMode = false;
    var ttsLang = 'English';
    var chatTtsAudio = null;
    var mediaRecorder = null;
    var audioChunks = [];
    var isRecording = false;
    var lastSentViaMic = false;  // true when the next sendMessage came from mic input

    // ---- Session Storage helpers ----
    function saveToSession() {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(chatConversation));
            sessionStorage.setItem(STORAGE_HTML_KEY, document.getElementById('chat-messages').innerHTML);
            sessionStorage.setItem(STORAGE_LANG_KEY, currentLang);
            sessionStorage.setItem(STORAGE_OPEN_KEY, chatOpen ? '1' : '0');
            sessionStorage.setItem(STORAGE_LISTEN_KEY, listenMode ? '1' : '0');
            sessionStorage.setItem(STORAGE_TTS_LANG_KEY, ttsLang);
        } catch(e) { /* quota exceeded - ignore */ }
    }

    function restoreFromSession() {
        try {
            var saved = sessionStorage.getItem(STORAGE_KEY);
            var savedHtml = sessionStorage.getItem(STORAGE_HTML_KEY);
            var savedLang = sessionStorage.getItem(STORAGE_LANG_KEY);
            var wasOpen = sessionStorage.getItem(STORAGE_OPEN_KEY);
            var savedListen = sessionStorage.getItem(STORAGE_LISTEN_KEY);
            var savedTtsLang = sessionStorage.getItem(STORAGE_TTS_LANG_KEY);

            if (saved && savedHtml) {
                chatConversation = JSON.parse(saved);
                document.getElementById('chat-messages').innerHTML = savedHtml;
                if (savedLang) {
                    currentLang = savedLang;
                    updateUILanguage(currentLang);
                }
                if (wasOpen === '1') {
                    chatOpen = true;
                    document.getElementById('chat-window').style.display = 'flex';
                    document.getElementById('chat-fab-icon').textContent = '\u2715';
                }
                // Restore scroll
                var container = document.getElementById('chat-messages');
                container.scrollTop = container.scrollHeight;
            }

            // Restore listen mode
            if (savedListen === '1') {
                listenMode = true;
                applyListenModeUI();
            }
            if (savedTtsLang) {
                ttsLang = savedTtsLang;
                applyTtsLangUI();
            }

            return !!(saved && savedHtml);
        } catch(e) { /* parse error - start fresh */ }
        return false;
    }

    // ---- Language UI updater ----
    function updateUILanguage(lang) {
        var strings = UI_STRINGS[lang] || UI_STRINGS.en;
        currentLang = lang;

        // Update chips
        var chips = document.querySelectorAll('.chat-chip');
        if (chips.length >= 3) {
            chips[0].textContent = strings.chip1;
            chips[0].setAttribute('onclick', "sendQuickMessage('" + strings.chip1_msg.replace(/'/g, "\\'") + "')");
            chips[1].textContent = strings.chip2;
            chips[1].setAttribute('onclick', "sendQuickMessage('" + strings.chip2_msg.replace(/'/g, "\\'") + "')");
            chips[2].textContent = strings.chip3;
            chips[2].setAttribute('onclick', "sendQuickMessage('" + strings.chip3_msg.replace(/'/g, "\\'") + "')");
        }

        // Update input placeholder
        var input = document.getElementById('chat-input');
        if (input) input.placeholder = strings.placeholder;

        // Update language badge
        var langNames = {en: 'EN', zh: '中文', ms: 'BM', ta: 'தமிழ்'};
        var badge = document.getElementById('chat-lang-badge');
        if (badge) badge.textContent = langNames[lang] || lang.toUpperCase();
    }

    // ---- Listen mode ----
    function applyListenModeUI() {
        var btn = document.getElementById('chat-listen-btn');
        var bar = document.getElementById('chat-tts-lang-bar');
        if (btn) {
            btn.style.opacity = listenMode ? '1' : '0.6';
            btn.style.background = listenMode ? 'rgba(255,255,255,0.25)' : 'none';
            btn.style.borderRadius = '50%';
            btn.style.padding = listenMode ? '3px 5px' : '0 4px';
        }
        if (bar) bar.style.display = listenMode ? 'flex' : 'none';
    }

    function applyTtsLangUI() {
        document.querySelectorAll('.tts-lang-chip').forEach(function(chip) {
            chip.classList.toggle('active', chip.getAttribute('data-lang') === ttsLang);
        });
    }

    window.toggleListenMode = function() {
        listenMode = !listenMode;
        applyListenModeUI();
        saveToSession();
    };

    // TTS lang chip clicks
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('tts-lang-chip')) {
            ttsLang = e.target.getAttribute('data-lang');
            applyTtsLangUI();
            saveToSession();
        }
    });

    var LANG_TO_TTS_NAME = {en: 'English', zh: 'Chinese', ms: 'Malay', ta: 'Tamil'};

    // ---- TTS playback ----
    async function speakBotResponse(text) {
        if (!text) return;
        try {
            if (chatTtsAudio) { chatTtsAudio.pause(); chatTtsAudio = null; }
            var sourceLang = LANG_TO_TTS_NAME[currentLang] || 'English';
            var res = await fetch('/api/tts', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ text: text, language: ttsLang, source_language: sourceLang })
            });
            if (!res.ok) return;
            var blob = await res.blob();
            var url = URL.createObjectURL(blob);
            chatTtsAudio = new Audio(url);
            chatTtsAudio.onended = function() { URL.revokeObjectURL(url); chatTtsAudio = null; };
            chatTtsAudio.play().catch(function(e) {
                console.warn('Autoplay blocked — use the speaker button to play:', e.message);
                URL.revokeObjectURL(url);
                chatTtsAudio = null;
            });
        } catch(e) {
            console.warn('Chat TTS error:', e);
        }
    }

    // ---- Microphone / STT (MediaRecorder → Meralion server transcription) ----
    window.toggleMic = function() {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    };

    function startRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Microphone not supported in this browser.');
            return;
        }
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function(stream) {
                audioChunks = [];
                var mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                    ? 'audio/webm;codecs=opus'
                    : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '');
                var options = mimeType ? { mimeType: mimeType } : {};
                mediaRecorder = new MediaRecorder(stream, options);

                mediaRecorder.ondataavailable = function(e) {
                    if (e.data.size > 0) audioChunks.push(e.data);
                };

                mediaRecorder.onstop = function() {
                    stream.getTracks().forEach(function(t) { t.stop(); });
                    var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                    console.log('[Mic] Audio blob size:', blob.size, 'bytes, type:', blob.type);
                    if (blob.size < 500) {
                        // Recording too short / empty
                        var s = UI_STRINGS[currentLang] || UI_STRINGS.en;
                        appendMessage('bot', s.micNoAudio);
                        return;
                    }
                    transcribeViaServer(blob);
                };

                mediaRecorder.start();
                isRecording = true;
                setMicUI(true);
            })
            .catch(function(err) {
                console.error('Mic error:', err);
                var s = UI_STRINGS[currentLang] || UI_STRINGS.en;
                appendMessage('bot', s.micError);
            });
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        isRecording = false;
        setMicUI(false);
    }

    function setMicUI(recording) {
        var btn = document.getElementById('chat-mic-btn');
        if (!btn) return;
        if (recording) {
            btn.classList.add('recording');
            btn.title = 'Stop recording';
        } else {
            btn.classList.remove('recording');
            btn.title = 'Speak your message';
        }
    }

    // Meralion server transcription
    function transcribeViaServer(blob) {
        var micBtn = document.getElementById('chat-mic-btn');
        if (micBtn) { micBtn.classList.add('processing'); micBtn.disabled = true; }

        var formData = new FormData();
        var ext = blob.type.includes('webm') ? 'webm' : 'ogg';
        formData.append('audio', blob, 'voice.' + ext);

        fetch('/api/chat/transcribe', {
            method: 'POST',
            body: formData
        })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (micBtn) { micBtn.classList.remove('processing'); micBtn.disabled = false; }
            if (data.transcript && data.transcript.trim()) {
                var input = document.getElementById('chat-input');
                input.value = data.transcript.trim();
                lastSentViaMic = true;
                sendMessage();
            } else {
                var s = UI_STRINGS[currentLang] || UI_STRINGS.en;
                appendMessage('bot', s.micNoAudio);
            }
        })
        .catch(function(err) {
            if (micBtn) { micBtn.classList.remove('processing'); micBtn.disabled = false; }
            console.error('Transcription error:', err);
            var s = UI_STRINGS[currentLang] || UI_STRINGS.en;
            appendMessage('bot', s.micError);
        });
    }

    // ---- Initialize: restore session or show welcome ----
    restoreFromSession();

    window.toggleChat = function() {
        var win = document.getElementById('chat-window');
        var fab = document.getElementById('chat-fab-icon');
        chatOpen = !chatOpen;
        win.style.display = chatOpen ? 'flex' : 'none';
        fab.textContent = chatOpen ? '\u2715' : '\uD83D\uDCAC';
        saveToSession();
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
        saveToSession();

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

        var strings = UI_STRINGS[currentLang] || UI_STRINGS.en;

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
                appendMessage('bot', strings.errorPrefix + data.error);
                saveToSession();
                return;
            }

            // Update language UI on every response
            if (data.language) {
                currentLang = data.language;
                updateUILanguage(currentLang);
                // Auto-sync TTS voice to detected language when mic was used
                if (lastSentViaMic) {
                    var langToTts = {en: 'English', zh: 'Chinese', ms: 'Malay', ta: 'Tamil'};
                    ttsLang = langToTts[data.language] || ttsLang;
                    applyTtsLangUI();
                }
            }

            if (data.referred) {
                document.getElementById('chat-risk-alert').style.display = 'block';
            }

            var riskNote = '';
            if (data.risk_score >= 4 && data.risk_score < 7) {
                var riskStrings = UI_STRINGS[currentLang] || UI_STRINGS.en;
                riskNote = riskStrings.moderateRisk;
            }

            var fullResponse = data.response + riskNote;
            appendMessage('bot', fullResponse);
            chatConversation.push({role: 'assistant', content: data.response});
            saveToSession();

            // Speak if mic was used (voice-in = voice-out) or listen mode is on
            if (lastSentViaMic || listenMode) {
                speakBotResponse(data.response);
            }
            lastSentViaMic = false;
        })
        .catch(function(err) {
            removeTyping(typingEl);
            sendBtn.disabled = false;
            lastSentViaMic = false;
            appendMessage('bot', strings.errorConnect);
            saveToSession();
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

    window.addEventListener('beforeunload', function() {
        // Save state on navigation (session storage persists)
    });

    window.clearChatHistory = function() {
        chatConversation = [];
        currentLang = 'en';
        if (chatTtsAudio) { chatTtsAudio.pause(); chatTtsAudio = null; }
        sessionStorage.removeItem(STORAGE_KEY);
        sessionStorage.removeItem(STORAGE_HTML_KEY);
        sessionStorage.removeItem(STORAGE_LANG_KEY);
        sessionStorage.removeItem(STORAGE_OPEN_KEY);
        // Keep listen mode preference across clears
        fetch('/api/chat/clear', { method: 'POST', headers: {'Content-Type': 'application/json'} }).catch(function(){});
        var container = document.getElementById('chat-messages');
        var strings = UI_STRINGS.en;
        container.innerHTML =
            '<div class="chat-msg bot"><div class="chat-bubble bot-bubble">' +
            strings.welcome +
            '<ul style="margin: 8px 0 0 0; padding-left: 18px; font-size: 0.85rem;">' +
            '<li>' + strings.item1 + '</li>' +
            '<li>' + strings.item2 + '</li>' +
            '<li>' + strings.item3 + '</li></ul>' +
            '<div style="font-size: 0.8rem; color: #888; margin-top: 8px;">' + strings.langNote + '</div>' +
            '</div></div>';
        updateUILanguage('en');
    };
})();
