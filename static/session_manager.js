/**
 * Unified Session Manager - Handles both General and KERAAL pipelines
 */

class RehabSessionManager {
    constructor() {
        this.video = document.querySelector("video");
        this.canvas = document.createElement("canvas");
        this.ctx = this.canvas.getContext("2d");
        this.pipelineType = null; // 'general' or 'keraal'
        this.isRunning = false;
        this.language = 'English';
        this.pollInterval = null;
        this.frameScoringBuffer = [];
    }

    /**
     * Initialize the pipeline based on type
     */
    async initializePipeline(pipelineType = 'general') {
        console.log(`🚀 Initializing pipeline: ${pipelineType}`);
        this.pipelineType = pipelineType;

        if (pipelineType === 'general') {
            await this.startGeneralSession();
        } else if (pipelineType === 'keraal') {
            await this.startKeraalSession();
        }

        this.isRunning = true;
        this.startPolling();
    }

    /**
     * Start general rehabilitation session
     */
    async startGeneralSession() {
        try {
            const response = await fetch("/api/session/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    threshold: 30.0,
                    language: this.language
                })
            });
            const data = await response.json();
            console.log("✅ General session started", data);
        } catch (error) {
            console.error("❌ Error starting general session:", error);
        }
    }

    /**
     * Start KERAAL session (low back pain)
     */
    async startKeraalSession() {
        try {
            const response = await fetch("/api/session/start/keraal", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    language: this.language
                })
            });
            const data = await response.json();
            console.log("✅ KERAAL session started", data);
        } catch (error) {
            console.error("❌ Error starting KERAAL session:", error);
        }
    }

    /**
     * Grab frame from video and convert to base64 data URL
     */
    grabFrameDataURL() {
        if (!this.video || !this.video.videoWidth) return null;
        
        const w = this.video.videoWidth;
        const h = this.video.videoHeight;
        this.canvas.width = w;
        this.canvas.height = h;
        this.ctx.drawImage(this.video, 0, 0, w, h);
        return this.canvas.toDataURL("image/jpeg", 0.85);
    }

    /**
     * Process single frame based on pipeline type
     */
    async processFrame() {
        const frame_b64 = this.grabFrameDataURL();
        if (!frame_b64) return null;

        const endpoint = this.pipelineType === 'keraal'
            ? "/api/live_feedback_keraal"
            : "/api/live_feedback";

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    frame_b64,
                    language: this.language,
                    mode: this.pipelineType === 'keraal' ? 'auto' : 'auto',
                    pipeline: this.pipelineType
                })
            });

            if (!response.ok) {
                console.error(`API error: ${response.status}`);
                return null;
            }

            const output = await response.json();
            return output;
        } catch (error) {
            console.error("❌ Frame processing error:", error);
            return null;
        }
    }

    /**
     * Render score and form status on UI
     */
    renderStatus(frameScore, formStatus, pipelineType) {
        // Update score
        const scoreElement = document.getElementById("frameScoreText") || 
                            document.querySelector("[data-score]");
        if (scoreElement) {
            scoreElement.textContent = frameScore.toFixed(2);
            scoreElement.dataset.score = frameScore;
        }

        // Update form status badge
        const badge = document.getElementById("formStatusBadge") || 
                     document.querySelector("[data-form-status]");
        if (badge) {
            const isCorrect = formStatus === "CORRECT";
            
            badge.className = isCorrect ? "status-badge correct" : "status-badge incorrect";
            badge.textContent = isCorrect ? "✓ CORRECT FORM" : "✗ INCORRECT FORM";
            badge.dataset.formStatus = formStatus;

            // Add pipeline indicator
            badge.setAttribute("data-pipeline", pipelineType);
        }

        // Update correctness for KERAAL
        if (pipelineType === 'keraal') {
            const correctnessElement = document.querySelector("[data-correctness]");
            if (correctnessElement) {
                correctnessElement.textContent = (frameScore / 50).toFixed(2);
            }
        }
    }

    /**
     * Render feedback list
     */
    renderFeedback(feedbackItems) {
        const feedbackBox = document.getElementById("feedbackList") || 
                           document.querySelector("[data-feedback]");
        if (!feedbackBox) return;

        feedbackBox.innerHTML = "";
        (feedbackItems || []).slice(0, 4).forEach(txt => {
            const div = document.createElement("div");
            div.className = "feedback-item";
            div.textContent = txt;
            feedbackBox.appendChild(div);
        });
    }

    /**
     * Update rep counter display
     */
    updateRepCounter(repInfo) {
        if (!repInfo) return;

        // Current rep
        const repElement = document.querySelector("[data-rep-now]");
        if (repElement) {
            repElement.textContent = repInfo.rep_now;
            repElement.dataset.repNow = repInfo.rep_now;
        }

        // Rep target
        const repTargetElement = document.querySelector("[data-rep-target]");
        if (repTargetElement) {
            repTargetElement.textContent = repInfo.rep_target;
        }

        // Current set
        const setElement = document.querySelector("[data-set-now]");
        if (setElement) {
            setElement.textContent = repInfo.set_now;
            setElement.dataset.setNow = repInfo.set_now;
        }

        // Set target
        const setTargetElement = document.querySelector("[data-set-target]");
        if (setTargetElement) {
            setTargetElement.textContent = repInfo.set_target;
        }

        // Progress bar
        const progressBar = document.querySelector("[data-progress-bar]");
        if (progressBar) {
            const progress = (repInfo.rep_now / repInfo.rep_target) * 100;
            progressBar.style.width = Math.min(progress, 100) + "%";
        }

        // Show notifications for completed reps/sets
        if (repInfo.rep_incremented) {
            this.showNotification(`Rep ${repInfo.rep_now} complete!`);
        }
        if (repInfo.set_completed) {
            this.showNotification(`Set ${repInfo.set_now - 1} complete! Starting set ${repInfo.set_now}`);
        }
        if (repInfo.exercise_completed) {
            this.showNotification("🎉 Congratulations! Exercise completed!");
        }
    }

    /**
     * Show temporary notification
     */
    showNotification(message) {
        const notification = document.createElement("div");
        notification.className = "session-notification";
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 16px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10000;
            animation: slideInRight 0.3s ease;
        `;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3000);
    }

    /**
     * Start polling frames
     */
    startPolling() {
        if (this.pollInterval) clearInterval(this.pollInterval);

        this.pollInterval = setInterval(async () => {
            const output = await this.processFrame();
            if (!output) return;

            // Render UI updates
            this.renderStatus(output.frame_score, output.form_status, this.pipelineType);
            this.renderFeedback(output.llm_feedback || []);
            this.updateRepCounter(output.rep_info);

            // Log for debugging
            console.log(`[${this.pipelineType.toUpperCase()}]`, {
                score: output.frame_score,
                status: output.form_status,
                exercise: output.exercise_name,
                reps: output.rep_info
            });
        }, 500); // Poll every 500ms
    }

    /**
     * Stop polling
     */
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    /**
     * Stop session
     */
    async stopSession() {
        console.log(`🛑 Stopping ${this.pipelineType} session`);
        this.stopPolling();

        const endpoint = this.pipelineType === 'keraal'
            ? "/api/session/stop/keraal"
            : "/api/session/stop";

        try {
            await fetch(endpoint, { method: "POST" });
        } catch (error) {
            console.error("Error stopping session:", error);
        }

        this.isRunning = false;
    }

    /**
     * Reset for new exercise
     */
    async resetSession() {
        await this.stopSession();
        await this.initializePipeline(this.pipelineType);
    }
}

// Global instance
let rehabSessionManager = null;

/**
 * Initialize the rehab session with pipeline type selection
 */
async function initializeRehabSession(pipelineType = 'general') {
    if (rehabSessionManager) {
        await rehabSessionManager.stopSession();
    }

    rehabSessionManager = new RehabSessionManager();
    await rehabSessionManager.initializePipeline(pipelineType);
    return rehabSessionManager;
}

/**
 * Stop current session
 */
async function stopRehabSession() {
    if (rehabSessionManager) {
        await rehabSessionManager.stopSession();
    }
}
