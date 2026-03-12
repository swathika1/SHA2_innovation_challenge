/**
 * Jimmy Avatar Voice Interaction Client
 * Handles real-time voice-to-voice conversation with Jimmy
 * 
 * Features:
 * - Automatic voice activity detection (stops recording when you stop talking)
 * - Real-time transcription
 * - Automatic TTS playback of Jimmy's response
 * - Multilingual support
 */

class JimmyVoiceInteraction {
    constructor(options = {}) {
        this.audioContext = null;
        this.mediaStream = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.isProcessing = false;
        
        // Configuration
        this.sampleRate = 16000;
        this.language = options.language || 'English';
        this.endpoint = options.endpoint || '/patient/avatar/voice';
        this.conversationHistory = options.history || [];
        
        // Voice activity detection
        this.silenceThreshold = options.silenceThreshold || 30;  // dB
        this.silenceDuration = options.silenceDuration || 1000;  // ms
        this.speechStarted = false;
        this.lastSpeechTime = Date.now();
        
        // Callbacks
        this.onRecordingStart = options.onRecordingStart || (() => {});
        this.onRecordingEnd = options.onRecordingEnd || (() => {});
        this.onTranscribed = options.onTranscribed || (() => {});
        this.onResponse = options.onResponse || (() => {});
        this.onError = options.onError || (() => {});
        this.onAudioPlay = options.onAudioPlay || (() => {});
    }
    
    /**
     * Calculate audio energy level in dB
     */
    getAudioLevel(audioData) {
        const rms = Math.sqrt(
            audioData.reduce((sum, val) => sum + val * val, 0) / audioData.length
        );
        const db = 20 * Math.log10(rms + 1e-8);
        return db;
    }
    
    /**
     * Initialize audio recording
     */
    async initialize() {
        try {
            // Get user's microphone
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: false,  // We want raw audio for VAD
                    sampleRate: this.sampleRate
                }
            });
            
            // Create AudioContext for level monitoring
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            return true;
        } catch (error) {
            this.onError(`Microphone access denied: ${error.message}`);
            return false;
        }
    }
    
    /**
     * Start recording with automatic voice activity detection
     */
    async startRecording() {
        if (!this.mediaStream) {
            await this.initialize();
        }
        
        if (this.isRecording) return;
        
        this.audioChunks = [];
        this.isRecording = true;
        this.speechStarted = false;
        this.lastSpeechTime = Date.now();
        
        // Create MediaRecorder
        this.mediaRecorder = new MediaRecorder(this.mediaStream);
        
        // Monitor audio levels for speech detection
        const analyser = this.audioContext.createAnalyser();
        const source = this.audioContext.createMediaStreamSource(this.mediaStream);
        source.connect(analyser);
        analyser.fftSize = 2048;
        
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        
        // More aggressive speech detection
        const monitor = () => {
            if (!this.isRecording) return;
            
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
            
            // Lower threshold = more sensitive to speech
            const isSound = average > 20;  // More sensitive
            
            if (isSound) {
                this.speechStarted = true;
                this.lastSpeechTime = Date.now();
            }
            
            // Check if silence detected (speech ended) — MUCH MORE AGGRESSIVE
            if (this.speechStarted && 
                Date.now() - this.lastSpeechTime > this.silenceDuration) {
                console.log("[VAD] Speech ended - stopping recording");
                this.stopRecording();
                return;
            }
            
            requestAnimationFrame(monitor);
        };
        
        this.mediaRecorder.ondataavailable = (event) => {
            this.audioChunks.push(event.data);
        };
        
        this.mediaRecorder.onstop = () => {
            this.processRecordedAudio();
        };
        
        this.mediaRecorder.start();
        this.onRecordingStart();
        monitor();  // Start monitoring audio
    }
    
    /**
     * Stop recording
     */
    stopRecording() {
        if (this.isRecording && this.mediaRecorder) {
            this.isRecording = false;
            this.mediaRecorder.stop();
            this.onRecordingEnd();
        }
    }
    
    /**
     * Process recorded audio and send to server
     */
    async processRecordedAudio() {
        if (this.audioChunks.length === 0) return;
        
        this.isProcessing = true;
        
        try {
            // Convert audio chunks to base64
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            const arrayBuffer = await audioBlob.arrayBuffer();
            const uint8Array = new Uint8Array(arrayBuffer);
            const binaryString = String.fromCharCode.apply(null, uint8Array);
            const base64Audio = btoa(binaryString);
            
            // Send to server
            const response = await fetch(this.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    audio: base64Audio,
                    language: this.language,
                    history: this.conversationHistory
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Server error');
            }
            
            const result = await response.json();
            
            if (result.status !== 'success') {
                throw new Error(result.error || 'Processing failed');
            }
            
            // Update conversation history
            if (result.transcribed_text) {
                this.conversationHistory.push({
                    role: 'user',
                    content: result.transcribed_text
                });
                this.onTranscribed(result.transcribed_text);
            }
            
            // Handle Jimmy's response
            if (result.response) {
                this.conversationHistory.push({
                    role: 'assistant',
                    content: result.response
                });
                this.onResponse(result.response);
                
                // Play audio response if available
                if (result.response_audio) {
                    await this.playAudioResponse(result.response_audio);
                }
            }
        } catch (error) {
            this.onError(`Error: ${error.message}`);
        } finally {
            this.isProcessing = false;
        }
    }
    
    /**
     * Play TTS audio response from server
     */
    async playAudioResponse(base64Audio) {
        try {
            // Decode base64 to blob
            const binaryString = atob(base64Audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const audioBlob = new Blob([bytes], { type: 'audio/mpeg' });
            const audioUrl = URL.createObjectURL(audioBlob);
            
            // Create and play audio element
            const audio = new Audio(audioUrl);
            audio.onplay = () => this.onAudioPlay(true);
            audio.onended = () => this.onAudioPlay(false);
            await audio.play();
        } catch (error) {
            console.error('Error playing audio:', error);
        }
    }
    
    /**
     * Start voice conversation (automatically stops and responds)
     */
    async startConversation() {
        // Prevent multiple simultaneous requests
        if (this.isRecording || this.isProcessing) {
            return;
        }
        
        // Start recording automatically
        await this.startRecording();
        // No need to wait or check - VAD will automatically stop when speech ends
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        if (this.mediaRecorder) {
            this.mediaRecorder.stop();
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}


// ────────────────────────────────────────────────────────────────────────
// HTML INTEGRATION EXAMPLE
// ────────────────────────────────────────────────────────────────────────

/*
<!-- In your template, add this HTML: -->

<div id="avatar-voice-container" class="avatar-voice">
    <div class="avatar-interface">
        <img id="avatar-image" src="/static/avatars/jimmy.png" alt="Jimmy Avatar" class="avatar-avatar">
        
        <div id="avatar-status" class="avatar-status">
            <div id="status-text" class="status-text">Ready to talk</div>
            <div id="recording-indicator" class="recording-indicator hidden">
                <div class="pulse"></div>
                Listening... (stop talking to respond)
            </div>
            <div id="processing-indicator" class="processing-indicator hidden">
                <div class="spinner"></div>
                Processing your request...
            </div>
        </div>
        
        <!-- ONLY ONE BUTTON - Click once to start, system handles the rest -->
        <button id="voice-btn" class="voice-btn">
            🎤 Talk to Jimmy
        </button>
        
        <div id="transcript" class="transcript hidden">
            <strong>You said:</strong> <span id="user-text"></span>
            <br><br>
            <strong>Jimmy says:</strong> <span id="jimmy-text"></span>
        </div>
    </div>
</div>

<script>
// Initialize voice interaction
const jimmy = new JimmyVoiceInteraction({
    language: 'English',  // Can be English, Chinese, Malay, Tamil, Singlish
    silenceDuration: 1000,  // 1 second of silence = end of speech
    
    onRecordingStart: () => {
        // Show listening state
        document.getElementById('status-text').textContent = '';
        document.getElementById('recording-indicator').classList.remove('hidden');
        document.getElementById('voice-btn').disabled = true;
        document.getElementById('voice-btn').textContent = '🎤 Listening...';
    },
    
    onRecordingEnd: () => {
        // Show processing state
        document.getElementById('recording-indicator').classList.add('hidden');
        document.getElementById('processing-indicator').classList.remove('hidden');
        document.getElementById('voice-btn').textContent = '⏳ Processing...';
    },
    
    onTranscribed: (text) => {
        console.log('Transcribed:', text);
        document.getElementById('user-text').textContent = text;
        document.getElementById('transcript').classList.remove('hidden');
    },
    
    onResponse: (response) => {
        console.log('Jimmy response:', response);
        document.getElementById('jimmy-text').textContent = response;
        document.getElementById('status-text').textContent = '🔊 Listening to response...';
    },
    
    onAudioPlay: (isPlaying) => {
        if (isPlaying) {
            document.getElementById('processing-indicator').classList.add('hidden');
            document.getElementById('status-text').textContent = '🔊 Listening to Jimmy...';
        } else {
            // Audio finished - ready for next interaction
            document.getElementById('status-text').textContent = 'Ready to talk';
            document.getElementById('voice-btn').disabled = false;
            document.getElementById('voice-btn').textContent = '🎤 Talk to Jimmy';
        }
    },
    
    onError: (error) => {
        console.error('Error:', error);
        document.getElementById('recording-indicator').classList.add('hidden');
        document.getElementById('processing-indicator').classList.add('hidden');
        document.getElementById('status-text').textContent = `Error: ${error}`;
        document.getElementById('voice-btn').disabled = false;
        document.getElementById('voice-btn').textContent = '🎤 Talk to Jimmy';
    }
});

// Initialize on load
document.addEventListener('DOMContentLoaded', async () => {
    await jimmy.initialize();
    
    document.getElementById('voice-btn').addEventListener('click', () => {
        // Single click - system handles everything automatically
        jimmy.startConversation();
    });
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    jimmy.destroy();
});
</script>

<style>
.avatar-voice {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 15px;
    min-height: 400px;
}

.avatar-interface {
    text-align: center;
    background: white;
    padding: 30px;
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    max-width: 400px;
}

.avatar-avatar {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    margin-bottom: 20px;
}

.avatar-status {
    margin: 20px 0;
    font-size: 14px;
    color: #666;
    min-height: 50px;
}

.status-text {
    margin-bottom: 10px;
    font-weight: bold;
}

.recording-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: #e74c3c;
    font-weight: bold;
}

.processing-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: #3498db;
    font-weight: bold;
}

.pulse {
    width: 10px;
    height: 10px;
    background: #e74c3c;
    border-radius: 50%;
    animation: pulse 1.5s infinite;
}

.spinner {
    width: 20px;
    height: 20px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #3498db;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.voice-btn {
    padding: 15px 30px;
    font-size: 16px;
    border: none;
    border-radius: 25px;
    background: #667eea;
    color: white;
    cursor: pointer;
    transition: all 0.3s;
    margin: 20px 0;
    min-width: 200px;
}

.voice-btn:hover:not(:disabled) {
    background: #764ba2;
    transform: scale(1.05);
}

.voice-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.transcript {
    margin-top: 20px;
    padding: 15px;
    background: #f5f5f5;
    border-radius: 10px;
    text-align: left;
    word-wrap: break-word;
}

.hidden {
    display: none !important;
}
</style>
*/
