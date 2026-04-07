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
        this.currentScreen = 'onboarding-1';
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
        this.enforceProfileImages();
        setTimeout(() => this.initChart(), 500);
        
        document.body.addEventListener('touchstart', function() {}, {passive: true});
        this.goToScreen('onboarding-1');
    }

    enforceProfileImages() {
        const profileAsset = 'assets/elderly-profile-80.svg?v=20260406';
        document.querySelectorAll('img[alt="Profile"], .profile-img, .profile-img-large').forEach((img) => {
            img.src = profileAsset;
            img.onerror = () => {
                img.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"%3E%3Crect width="256" height="256" rx="128" fill="%23e2e8f0"/%3E%3Ccircle cx="128" cy="128" r="56" fill="%2394a3b8"/%3E%3C/svg%3E';
            };
        });
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

        const bottomNav = document.querySelector('.bottom-nav');
        if (bottomNav) {
            const navScreens = new Set([
                'dashboardScreen',
                'exerciseListScreen',
                'voiceScreen',
                'profileScreen',
                'chatbotScreen'
            ]);
            bottomNav.style.display = navScreens.has(screenId) ? 'flex' : 'none';
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
    goToOnboarding(step) {
        this.goToScreen('onboarding-' + step);
    }

    goToLogin() {
        this.goToScreen('login-screen');
    }

    selectRole(role) {
        this.selectedRole = role;
        if (role === 'patient') {
            this.goToScreen('login-screen');
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
        userMsg.style.cssText = 'background: linear-gradient(135deg, #5B8CFF 0%, #7B61FF 100%); padding:16px; border-radius:12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); align-self: flex-end; max-width: 85%; color:white;';
        userMsg.textContent = message;
        messagesDiv.appendChild(userMsg);
        
        input.value = '';
        
        // Add a professional intake-style bot reply after a short delay.
        setTimeout(() => {
            const botMsg = document.createElement('div');
            botMsg.style.cssText = 'background:white;padding:16px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.05);align-self:flex-start;max-width:85%;color:#1F2937;font-size:14px;line-height:1.5;';
            botMsg.innerHTML = '<strong>RehabCoach Clinical Assistant</strong><br/><br/>Thank you for your message. I will help you with a structured rehabilitation response.<br/><br/>Please share the following so I can assess your condition safely:<br/>1. Primary symptom and affected body region<br/>2. Time of onset and whether it was sudden or gradual<br/>3. Pain score (0-10)<br/>4. Movements or activities that aggravate the symptom<br/>5. Associated signs: swelling, numbness, weakness, fever, recent fall, or injury<br/><br/>After this, I will provide a clear plan with immediate advice, precautions, and recommended next steps. If you have severe pain, chest pain, breathing difficulty, or rapidly worsening symptoms, seek urgent medical care immediately.';
            messagesDiv.appendChild(botMsg);
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
            
            // Start skeleton detection
            this.initPoseDetection();
        } catch (err) {
            console.error('Camera error:', err);
            alert('Camera permissions are required for posture tracking.');
            this.goToScreen('exerciseListScreen');
        }
    }

    async initPoseDetection() {
        try {
            const video = document.getElementById('cameraFeed');
            const canvas = document.getElementById('skeletonOverlay');
            
            if (!canvas) return; // Canvas might not be ready yet
            
            // Use COCO-SSD or a simple pose detection
            // For now, just draw a simple skeleton frame detection indicator
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            
            const ctx = canvas.getContext('2d');
            
            // Draw skeleton nodes (simplified visualization)
            const drawSkeleton = async () => {
                if (!this.videoStream) return;
                
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.strokeStyle = '#00FF41';
                ctx.lineWidth = 2;
                ctx.fillStyle = '#00FF4166';
                
                // Draw detecting skeleton indicator
                ctx.font = 'bold 16px Arial';
                ctx.fillStyle = '#00FF41';
                ctx.fillText('🔍 Person Detected', 10, 30);
                
                // Draw simple skeleton frame (circle nodes at key points)
                const joints = [
                    {x: canvas.width/2 - 40, y: canvas.height/4},      // head
                    {x: canvas.width/2, y: canvas.height/3},            // shoulder
                    {x: canvas.width/2 - 60, y: canvas.height/2},       // left elbow
                    {x: canvas.width/2 + 60, y: canvas.height/2},       // right elbow
                    {x: canvas.width/2 - 50, y: canvas.height * 0.7},   // left knee
                    {x: canvas.width/2 + 50, y: canvas.height * 0.7},   // right knee
                ];
                
                // Draw connections
                ctx.strokeStyle = '#00FF41';
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.moveTo(joints[1].x, joints[1].y);
                ctx.lineTo(joints[2].x, joints[2].y);
                ctx.lineTo(joints[4].x, joints[4].y);
                ctx.stroke();
                
                ctx.beginPath();
                ctx.moveTo(joints[1].x, joints[1].y);
                ctx.lineTo(joints[3].x, joints[3].y);
                ctx.lineTo(joints[5].x, joints[5].y);
                ctx.stroke();
                
                // Draw joint circles
                joints.forEach(joint => {
                    ctx.fillStyle = '#00FF41';
                    ctx.beginPath();
                    ctx.arc(joint.x, joint.y, 5, 0, Math.PI * 2);
                    ctx.fill();
                });
                
                requestAnimationFrame(drawSkeleton);
            };
            
            drawSkeleton();
        } catch (err) {
            console.error('Pose detection error:', err);
        }
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

function goToOnboarding(step) {
    document.querySelectorAll('.onboarding-screen').forEach(el => {
        el.style.display = 'none';
        el.classList.remove('active');
    });
    const onboardingScreen = document.getElementById('onboarding-' + step);
    if (onboardingScreen) {
        onboardingScreen.style.display = 'block';
        onboardingScreen.classList.add('active');
    }
}

function goToLogin() {
    document.querySelectorAll('.onboarding-screen').forEach(el => {
        el.style.display = 'none';
        el.classList.remove('active');
    });
    const loginScreen = document.getElementById('login-screen');
    if (loginScreen) {
        loginScreen.style.display = 'block';
        loginScreen.classList.add('active');
    }
}

window.goToOnboarding = goToOnboarding;
window.goToLogin = goToLogin;

window.onload = () => {
    window.app = new App();
    if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }
};