/**
 * SHA2 Mobile App - API Client Service Layer
 * Centralizes all backend API calls
 * Preserves all existing backend functionality
 */

class APIClient {
    constructor() {
        this.baseURL = window.location.origin;
        this.timeout = 10000;
    }

    /**
     * Generic fetch wrapper with timeout
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                }
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const error = await response.text();
                throw new Error(`${response.status}: ${error}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            console.error(`API Error [${endpoint}]:`, error.message);
            throw error;
        }
    }

    /**
     * AUTHENTICATION
     */
    async login(email, password, role = 'patient') {
        return this.request('/api/login', {
            method: 'POST',
            body: JSON.stringify({ email, password, role })
        });
    }

    async signup(formData) {
        return this.request('/api/signup', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
    }

    async logout() {
        return this.request('/api/logout', { method: 'POST' });
    }

    async getCurrentUser() {
        return this.request('/api/current-user');
    }

    /**
     * EXERCISE & SESSION
     */
    async getExercises() {
        return this.request('/api/patient/exercises');
    }

    async startSession() {
        return this.request('/patient/session', { method: 'GET' });
    }

    /**
     * POSE DETECTION & FEEDBACK
     * Sends camera frame to ML model
     */
    async sendFrameForPoseFeedback(frameData) {
        const formData = new FormData();
        formData.append('frame', frameData);
        
        return fetch(`${this.baseURL}/api/live_feedback`, {
            method: 'POST',
            body: formData
        }).then(r => r.json());
    }

    /**
     * VOICE FEEDBACK
     */
    async getVoiceFeedback(text) {
        return this.request('/api/tts', {
            method: 'POST',
            body: JSON.stringify({ text })
        });
    }

    /**
     * SESSION MANAGEMENT
     */
    async saveSession(sessionData) {
        return this.request('/api/session/save', {
            method: 'POST',
            body: JSON.stringify(sessionData)
        });
    }

    async getSessionReport(sessionId) {
        return this.request(`/api/session/report/${sessionId}`);
    }

    /**
     * REPORTS & ANALYTICS
     */
    async getPatientReports() {
        return this.request('/api/patient/reports');
    }

    async getDoctorPatients() {
        return this.request('/api/doctor/patients');
    }

    async getPatientReport(patientId) {
        return this.request(`/api/session/report/doctor/${patientId}`);
    }

    /**
     * APPOINTMENTS
     */
    async getAppointments() {
        return this.request('/api/appointments');
    }

    async scheduleAppointment(appointmentData) {
        return this.request('/api/appointments', {
            method: 'POST',
            body: JSON.stringify(appointmentData)
        });
    }

    /**
     * VIDEO CALLING
     */
    async initiateVideoCall(recipientId) {
        return this.request('/api/video/call/initiate', {
            method: 'POST',
            body: JSON.stringify({ recipient_id: recipientId })
        });
    }

    async getVideoCallDetails(callId) {
        return this.request(`/api/video/call/${callId}`);
    }

    /**
     * CHATBOT
     */
    async getChatbotResponse(message) {
        return this.request('/api/chat', {
            method: 'POST',
            body: JSON.stringify({ message })
        });
    }

    /**
     * CAREGIVER ENDPOINTS
     */
    async getCaregiverPatients() {
        return this.request('/api/caregiver/patients');
    }

    async getPatientStatus(patientId) {
        return this.request(`/api/caregiver/patient/${patientId}`);
    }
}

// Export singleton
const api = new APIClient();
