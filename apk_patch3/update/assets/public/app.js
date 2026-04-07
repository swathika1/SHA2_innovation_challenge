const langStrings = {
    en: {
        greeting: "How can I help you today, Ah Mei?",
        subtitle: "Tap the microphone to speak",
        responses: [
            "Your progress looks great. Don't forget to take it easy if you feel pain.",
            "I'm here for you. Please let me know how you are feeling.",
            "You have 3 exercises remaining today. Would you like to start with Lateral Trunk Tilt?",
            "Keep your back straight and slow down your movement."
        ]
    },
    zh: {
        greeting: "阿妹，今天我能怎么帮您？",
        subtitle: "点击麦克风说话",
        responses: [
            "您的进度很好。如果感到疼痛，请随时休息。",
            "我在这里。请告诉我您的感觉。",
            "今天您还有 3 个练习。您想从侧躯干倾斜开始吗？",
            "保持背部直立，动作慢一点。"
        ]
    },
    ta: {
        greeting: "ஆ மே, இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?",
        subtitle: "பேச மைக்ரோஃபோனைத் தட்டவும்",
        responses: [
            "உங்கள் முன்னேற்றம் நன்றாக உள்ளது.",
            "நான் உங்களுக்காக இங்கே இருக்கிறேன்.",
            "இன்று நீங்கள் 3 பயிற்சிகளை முடிக்க வேண்டும்.",
            "உங்கள் முதுகை நேராக வையுங்கள்."
        ]
    },
    ms: {
        greeting: "Bagaimana saya boleh membantu anda hari ini, Ah Mei?",
        subtitle: "Ketik mikrofon untuk bercakap",
        responses: [
            "Kemajuan anda nampak hebat. Jangan lupa berehat jika anda berasa sakit.",
            "Saya ada di sini. Sila beritahu saya perasaan anda.",
            "Anda mempunyai 3 latihan baki hari ini.",
            "Pastikan belakang anda lurus dan perlahan pergerakan."
        ]
    }
};

class App {
    constructor() {
        this.currentScreen = 'onboardingScreen';
        this.onboardingStep = 0;
        this.videoStream = null;
        this.isRecording = false;
        this.repCount = 0;
        this.currentLang = 'en';
        this.selectedRole = null;
        
        // Voice Setup
        this.recognition = null;
        this.isListening = false;
        this.synth = window.speechSynthesis;
        
        this.initVoiceApi();
        setTimeout(() => this.initChart(), 500);
        
        document.body.addEventListener('touchstart', function() {}, {passive: true});
        this.goToScreen('onboardingScreen');
    }

    setLanguage(lang) {
        this.currentLang = lang;
        if(langStrings[lang]) {
            document.querySelector('.t_greeting').textContent = langStrings[lang].greeting;
            document.querySelector('.t_subtitle').textContent = langStrings[lang].subtitle;
        }
    }

    goToScreen(screenId) {
        document.querySelectorAll('.screen').forEach(s => {
            s.classList.remove('active');
            setTimeout(() => s.style.transform = '', 300);
        });
        
        const nextScreen = document.getElementById(screenId);
        if(nextScreen) {
            nextScreen.classList.add('active');
        }
        
        if (this.currentScreen === 'exerciseCameraScreen' && screenId !== 'exerciseCameraScreen') {
            this.stopCamera();
        }
        if (this.currentScreen === 'voiceScreen' && screenId !== 'voiceScreen') {
            this.stopVoice();
        }
        
        this.currentScreen = screenId;
    }

    // --- ONBOARDING & AUTH ---
    nextOnboarding() {
        const slider = document.getElementById('onboardingSlider');
        this.onboardingStep++;
        
        if (this.onboardingStep > 2) {
            this.goToScreen('roleScreen');
            return;
        }

        slider.scrollTo({ left: this.onboardingStep * window.innerWidth, behavior: 'smooth' });
    }

    selectRole(role) {
        this.selectedRole = role;
        if (role === 'patient') {
            this.goToScreen('authScreen');
        } else {
            alert(`${role.charAt(0).toUpperCase() + role.slice(1)} access coming soon!`);
        }
    }

    login() {
        const btn = document.getElementById('loginBtn');
        const nricInput = document.getElementById('loginNric').value;
        if (nricInput) {
            localStorage.setItem('user_nric', nricInput);
            document.getElementById('profileNricDisplay').innerText = `NRIC: ${nricInput}`;
        }
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        setTimeout(() => {
            btn.innerHTML = 'Log In';
            this.goToScreen('dashboardScreen');
        }, 800);
    }

    sendChatMessage() {
        const input = document.getElementById('chatInput');
        const messagesDiv = document.getElementById('chatMessages');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Add user message
        const userMsg = document.createElement('div');
        userMsg.style.cssText = 'background: linear-gradient(135deg, #5B8CFF 0%, #7B61FF 100%); padding:14px; border-radius:12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); align-self: flex-end; max-width: 80%; color:white;';
        userMsg.textContent = message;
        messagesDiv.appendChild(userMsg);
        
        input.value = '';
        
        // Add static bot reply after a short delay
        setTimeout(() => {
            const replies = ['That's great progress. Please log your symptoms so I'll stay updated.'];
            
            const botMsg = document.createElement('div');
            botMsg.style.cssText = 'background: white; padding:14px; border-radius:12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); align-self: flex-start; max-width: 80%;';
            botMsg.textContent = replies[Math.floor(Math.random() * replies.length)];
            botMsg.style.color = '#1F2937';
            botMsg.style.fontSize = '14px';
            messagesDiv.appendChild(botMsg);
            
            // Scroll to bottom
            messagesDiv.parentElement.scrollTop = messagesDiv.parentElement.scrollHeight;
        }, 300);
    }

    // --- CAMERA & EXERCISE ---
    openExercise(name) {
        document.getElementById('camExerciseName').textContent = name;
        this.goToScreen('exerciseCameraScreen');
        this.startCamera();
    }

    async startCamera() {
        try {
            // Updated constraints for WebView stability
            this.videoStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 }, aspectRatio: 4/3 },
                audio: false
            });
            document.getElementById('cameraFeed').srcObject = this.videoStream;
            document.getElementById('camStatus').innerHTML = `<i class="fas fa-check-circle"></i> Ready`;
            document.getElementById('camStatus').className = 'status-badge good';
            document.getElementById('camRepCount').textContent = '0';
        } catch (err) {
            console.error('Camera error:', err);
            alert('Camera permissions are required for posture tracking.');
            this.goToScreen('exerciseListScreen');
        }
    }

    stopCamera() {
        if (this.videoStream) {
            this.videoStream.getTracks().forEach(t => t.stop());
            this.videoStream = null;
        }
        this.isRecording = false;
        const btn = document.getElementById('recordBtn');
        if (btn) {
            btn.classList.remove('recording');
            btn.innerHTML = '<i class="fas fa-play"></i> START';
        }
        const overlay = document.getElementById('skeletonOverlay');
        if (overlay) overlay.classList.remove('active');
    }

    toggleRecording() {
        this.isRecording = !this.isRecording;
        const btn = document.getElementById('recordBtn');
        const overlay = document.getElementById('skeletonOverlay');
        
        if (this.isRecording) {
            btn.classList.add('recording');
            btn.innerHTML = '<i class="fas fa-stop"></i> STOP';
            overlay.classList.add('active'); // Turn on skeletal overlay
            this.repCount = 0;
            document.getElementById('camRepCount').textContent = this.repCount;
            this.simulateAiModel();
            this.speak("Starting session. Please stand straight.");
        } else {
            btn.classList.remove('recording');
            btn.innerHTML = '<i class="fas fa-play"></i> START';
            overlay.classList.remove('active');
            document.getElementById('camStatus').innerHTML = '<i class="fas fa-flag-checkered"></i> Done';
            document.getElementById('camStatus').className = 'status-badge good';
            this.speak(`Session complete. Great job Ah Mei!`);
        }
    }

    simulateAiModel() {
        let step = 0;
        const interval = setInterval(() => {
            if (!this.isRecording) return clearInterval(interval);
            
            // Random simulated API latency and feedback logic (Failsafe mode fallback)
            if (Math.random() > 0.6) {
                const isGood = Math.random() > 0.4;
                const badge = document.getElementById('camStatus');
                
                if (isGood) {
                    badge.className = 'status-badge good';
                    badge.innerHTML = `<i class="fas fa-check-circle"></i> Good Posture`;
                } else {
                    badge.className = 'status-badge warning';
                    badge.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Keep back straight`;
                    if (Math.random() > 0.5) this.speak("Keep your back straight");
                }
            }

            step++;
            if (step % 5 === 0) { 
                this.repCount++;
                document.getElementById('camRepCount').textContent = this.repCount;
                
                // Simulate sending payload to /api/live_feedback
                fetch('/api/live_feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ rep_count: this.repCount, status: 'simulated_success' })
                }).catch(e => { /* Silently fail as requested, Failsafe mode works! */ });
            }
        }, 600);
    }

    // --- VOICE UI ---
    initVoiceApi() {
        const sr = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (sr) {
            this.recognition = new sr();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
        }
    }

    toggleVoice() { 
        this.isListening ? this.stopVoice() : this.startVoice(); 
    }

    startVoice() {
        if (!this.recognition) {
            alert("Speech recognition not supported on this browser.");
            return;
        }
        try {
            if (this.synth) this.synth.cancel();
            
            // Set dynamic lang
            const langMap = { 'en': 'en-US', 'zh': 'zh-CN', 'ta': 'ta-IN', 'ms': 'ms-MY' };
            this.recognition.lang = langMap[this.currentLang] || 'en-US';
            
            this.recognition.onresult = (e) => {
                const text = e.results[0][0].transcript;
                this.processVoiceCommand(text);
            };
            this.recognition.onend = () => this.stopVoiceUI();
            this.recognition.onerror = () => this.stopVoiceUI();

            this.recognition.start();
            this.isListening = true;
            
            document.getElementById('voiceTranscript').textContent = "Listening...";
            document.getElementById('voiceTranscript').style.color = "var(--primary)";
            document.querySelector('.waveform').classList.add('active');
            
            const micBtn = document.getElementById('micBtn');
            micBtn.style.transform = "scale(0.9)";
            micBtn.style.boxShadow = "0 0 30px rgba(79, 70, 229, 0.8)";
        } catch(e) { 
            console.error(e); 
        }
    }

    stopVoice() {
        if (this.recognition) this.recognition.stop();
        this.stopVoiceUI();
    }

    stopVoiceUI() {
        this.isListening = false;
        document.querySelector('.waveform').classList.remove('active');
        
        const micBtn = document.getElementById('micBtn');
        micBtn.style.transform = "scale(1)";
        micBtn.style.boxShadow = "0 10px 25px rgba(79, 70, 229, 0.4)";
    }

    processVoiceCommand(text) {
        // Don't record/display actual transcript for privacy
        document.getElementById('voiceTranscript').textContent = "✓ Message received";
        document.getElementById('voiceTranscript').style.color = "var(--success)";
        
        // Show loader
        document.getElementById('voiceLoader').style.display = "block";
        document.getElementById('voiceGreeting').style.opacity = "0.5";
        
        // Simulate API sending to Meralion / Jimmy engine
        setTimeout(() => {
            document.getElementById('voiceLoader').style.display = "none";
            document.getElementById('voiceGreeting').style.opacity = "1";
            
            const resArray = langStrings[this.currentLang] ? langStrings[this.currentLang].responses : langStrings.en.responses;
            // Pick a random simulated contextual response as fallback
            let reply = resArray[Math.floor(Math.random() * resArray.length)];
            
            if (this.currentLang === 'en' && text.toLowerCase().includes("pain")) {
                reply = "I'm sorry to hear that. Please rest immediately. I will log this for your doctor.";
            }
            
            document.getElementById('voiceGreeting').textContent = reply;
            this.speak(reply);
            
        }, 1500);
    }

    speak(text) {
        if (!this.synth) return;
        
        try {
            this.synth.cancel();
            
            const utterance = new SpeechSynthesisUtterance(text);
            const langMap = { 'en': 'en-US', 'zh': 'zh-CN', 'ta': 'ta-IN', 'ms': 'ms-MY' };
            utterance.lang = langMap[this.currentLang] || 'en-US';
            utterance.rate = 0.95;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            
            // Re-animate waveform during speech to feel "alive"
            utterance.onstart = () => {
                const waveform = document.querySelector('.waveform');
                if (waveform) waveform.classList.add('active');
            };
            utterance.onend = () => {
                const waveform = document.querySelector('.waveform');
                if (waveform) waveform.classList.remove('active');
            };
            
            this.synth.speak(utterance);
        } catch(e) {
            console.error("Speech synthesis failed:", e);
        }
    }

    // --- CHARTS ---
    initChart() {
        const ctx = document.getElementById('progressChart');
        if (!ctx) return;
        
        new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
                datasets: [{
                    label: 'Recovery Score',
                    data: [65, 70, 72, 78, 85, 88],
                    borderColor: '#4f46e5',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#ffffff',
                    pointBorderColor: '#4f46e5',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true, 
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { grid: { display: false }, border: { display: false }, ticks: { font: { size: 11, family: 'Inter' } } },
                    y: { grid: { color: '#f1f5f9', drawBorder: false }, border: { display: false }, ticks: { font: { size: 11, family: 'Inter' } } }
                },
                layout: { padding: 5 }
            }
        });
    }
}

window.onload = () => {
    window.app = new App();
    if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }
};