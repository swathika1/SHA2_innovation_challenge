/**
 * Gamification Engine for Rehabilitation Platform
 * Manages achievements, streaks, badges, and user engagement features
 */

class GamificationEngine {
    constructor() {
        this.repCount = 0;
        this.streak = 0;
        this.achievements = new Map();
        this.badges = {
            'first_rep': { name: 'First Step', icon: '👣', description: 'Complete your first rep', unlocked: false },
            'ten_reps': { name: 'Decade', icon: '10️⃣', description: 'Complete 10 reps in one session', unlocked: false },
            'fifty_reps': { name: 'Golden Standard', icon: '⭐', description: 'Complete 50 reps in one session', unlocked: false },
            'perfect_form': { name: 'Perfect Form', icon: '✨', description: '5 correct reps in a row', unlocked: false },
            'form_master': { name: 'Form Master', icon: '🏆', description: '10 correct reps in a row', unlocked: false },
            'streaker': { name: 'Streaker', icon: '🔥', description: 'Build a 5-rep streak', unlocked: false },
            'persistence': { name: 'Persistence Pays', icon: '💪', description: 'Complete 100 reps total', unlocked: false },
            'speedster': { name: 'Speedster', icon: '⚡', description: 'Complete 10 reps in 30 seconds', unlocked: false },
            'consistent': { name: 'Consistent Worker', icon: '📅', description: 'Exercise 5 days in a row', unlocked: false },
            'weekend_warrior': { name: 'Weekend Warrior', icon: '🎯', description: 'Exercise on a weekend', unlocked: false },
        };
        this.dailyChallenge = {
            goal: 20,
            current: 0,
            completed: false,
            bonus: 1.5,
        };
        this.soundEnabled = true;
        this.sessionStartTime = Date.now();
        this.lastRepTime = null;
        this.totalRepsAllTime = this.loadTotalReps();
        this.exerciseDays = this.loadExerciseDays();
    }

    /**
     * Record a new rep completion
     */
    recordRep(formIsCorrect = true) {
        this.repCount++;
        this.lastRepTime = Date.now();

        if (formIsCorrect) {
            this.streak++;
            this.dailyChallenge.current++;
            this.totalRepsAllTime++;
            this.saveTotalReps();
        } else {
            this.streak = 0;
        }

        this.checkAchievements();
        this.playSoundEffect('rep_success');
        
        return {
            repCount: this.repCount,
            streak: this.streak,
            newBadges: this.getUnlockedBadges(),
        };
    }

    /**
     * Check if any new achievements should be unlocked
     */
    checkAchievements() {
        // First rep
        if (this.repCount === 1) {
            this.unlockBadge('first_rep');
        }

        // Ten reps
        if (this.repCount === 10) {
            this.unlockBadge('ten_reps');
        }

        // Fifty reps
        if (this.repCount === 50) {
            this.unlockBadge('fifty_reps');
        }

        // Perfect form (5 correct in a row)
        if (this.streak === 5 && !this.badges.perfect_form.unlocked) {
            this.unlockBadge('perfect_form');
        }

        // Form master (10 correct in a row)
        if (this.streak === 10 && !this.badges.form_master.unlocked) {
            this.unlockBadge('form_master');
        }

        // Streaker (5-rep streak)
        if (this.streak === 5) {
            this.unlockBadge('streaker');
        }

        // Persistence (100 total reps)
        if (this.totalRepsAllTime >= 100) {
            this.unlockBadge('persistence');
        }

        // Speedster (10 reps in 30 seconds)
        const sessionDuration = (Date.now() - this.sessionStartTime) / 1000;
        if (this.repCount === 10 && sessionDuration <= 30) {
            this.unlockBadge('speedster');
        }

        // Daily challenge completion
        if (this.dailyChallenge.current >= this.dailyChallenge.goal) {
            this.dailyChallenge.completed = true;
            this.playSoundEffect('achievement_unlock');
        }
    }

    /**
     * Unlock a badge
     */
    unlockBadge(badgeKey) {
        if (this.badges[badgeKey] && !this.badges[badgeKey].unlocked) {
            this.badges[badgeKey].unlocked = true;
            this.playSoundEffect('badge_unlock');
            return true;
        }
        return false;
    }

    /**
     * Get all unlocked badges
     */
    getUnlockedBadges() {
        return Object.entries(this.badges)
            .filter(([_, badge]) => badge.unlocked)
            .map(([key, badge]) => ({ key, ...badge }));
    }

    /**
     * Play a sound effect
     */
    playSoundEffect(effectType) {
        if (!this.soundEnabled) return;

        const frequencies = {
            'rep_success': { freq: 800, duration: 0.15 },
            'achievement_unlock': { freq: 1200, duration: 0.3 },
            'badge_unlock': { freq: 1000, duration: 0.4 },
            'streak_milestone': { freq: 1400, duration: 0.2 },
        };

        const effect = frequencies[effectType];
        if (!effect) return;

        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.frequency.value = effect.freq;
            oscillator.type = 'sine';

            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(
                0.01,
                audioContext.currentTime + effect.duration
            );

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + effect.duration);
        } catch (e) {
            console.log('Audio context not available');
        }
    }

    /**
     * Get motivational message based on progress
     */
    getMotivationalMessage() {
        const messages = {
            0: "Let's get started! 💪",
            1: "Great! You've completed your first rep!",
            5: "Fantastic! Keep the momentum going! 🔥",
            10: "Awesome! You're crushing it! 🎉",
            20: "Incredible! You're on fire! 🌟",
            50: "Legend! You've hit 50 reps! 🏆",
        };

        // Find the appropriate message based on rep count
        const milestones = Object.keys(messages)
            .map(Number)
            .sort((a, b) => b - a);

        for (const milestone of milestones) {
            if (this.repCount >= milestone) {
                return messages[milestone];
            }
        }

        return "You've got this! 💪";
    }

    /**
     * Get session stats
     */
    getSessionStats() {
        const duration = ((Date.now() - this.sessionStartTime) / 1000).toFixed(1);
        const repsPerMinute = this.repCount > 0 ? (this.repCount / (duration / 60)).toFixed(1) : 0;

        return {
            duration,
            repCount: this.repCount,
            streak: this.streak,
            repsPerMinute,
            formScore: this.calculateFormScore(),
            dailyProgress: this.dailyChallenge.current / this.dailyChallenge.goal,
        };
    }

    /**
     * Calculate form score (0-100)
     */
    calculateFormScore() {
        if (this.repCount === 0) return 0;
        // In a real implementation, this would track incorrect reps
        return Math.max(0, 100 - (this.repCount - this.streak) * 5);
    }

    /**
     * Load total reps from localStorage
     */
    loadTotalReps() {
        const saved = localStorage.getItem('totalRepsAllTime');
        return saved ? parseInt(saved) : 0;
    }

    /**
     * Save total reps to localStorage
     */
    saveTotalReps() {
        localStorage.setItem('totalRepsAllTime', this.totalRepsAllTime.toString());
    }

    /**
     * Load exercise days from localStorage
     */
    loadExerciseDays() {
        const saved = localStorage.getItem('exerciseDays');
        return saved ? JSON.parse(saved) : [];
    }

    /**
     * Mark today as exercise day
     */
    markExerciseDay() {
        const today = new Date().toDateString();
        if (!this.exerciseDays.includes(today)) {
            this.exerciseDays.push(today);
            localStorage.setItem('exerciseDays', JSON.stringify(this.exerciseDays));
        }
    }

    /**
     * Get streak multiplier for daily challenge
     */
    getStreakMultiplier() {
        if (this.streak >= 10) return 2.0;
        if (this.streak >= 5) return 1.5;
        return 1.0;
    }

    /**
     * Reset session
     */
    resetSession() {
        this.repCount = 0;
        this.streak = 0;
        this.sessionStartTime = Date.now();
        this.lastRepTime = null;
    }

    /**
     * Reset daily challenge
     */
    resetDailyChallenge() {
        this.dailyChallenge.current = 0;
        this.dailyChallenge.completed = false;
    }

    /**
     * Export session data
     */
    exportSessionData() {
        return {
            timestamp: new Date().toISOString(),
            repCount: this.repCount,
            streak: this.streak,
            formScore: this.calculateFormScore(),
            duration: ((Date.now() - this.sessionStartTime) / 1000).toFixed(1),
            unlockedBadges: this.getUnlockedBadges(),
            dailyChallengeProgress: this.dailyChallenge.current,
        };
    }
}

/**
 * UI Controller for Gamification
 */
class GamificationUI {
    constructor(gamificationEngine, containerId = 'gamification-container') {
        this.engine = gamificationEngine;
        this.container = document.getElementById(containerId);
        this.init();
    }

    /**
     * Initialize UI elements
     */
    init() {
        if (!this.container) {
            console.error('Gamification container not found');
            return;
        }

        this.renderRepCounter();
        this.renderProgressRing();
        this.renderBadges();
        this.renderStreak();
        this.renderStats();
    }

    /**
     * Render rep counter
     */
    renderRepCounter() {
        const counterDiv = document.createElement('div');
        counterDiv.className = 'gamified-card rep-counter-container';
        counterDiv.innerHTML = `
            <div class="rep-number" id="rep-counter">${this.engine.repCount}</div>
            <div class="rep-label">Reps Completed</div>
            <div style="font-size: 14px; color: var(--text-light);" id="motivational-msg">
                ${this.engine.getMotivationalMessage()}
            </div>
        `;
        this.container?.appendChild(counterDiv);
    }

    /**
     * Render progress ring
     */
    renderProgressRing() {
        const ringDiv = document.createElement('div');
        ringDiv.className = 'progress-ring-container';
        ringDiv.innerHTML = `
            <svg class="progress-ring" width="180" height="180">
                <defs>
                    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
                        <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
                    </linearGradient>
                </defs>
                <circle class="progress-ring-bg" cx="90" cy="90" r="80"/>
                <circle class="progress-ring-circle" id="progress-circle" cx="90" cy="90" r="80"
                    style="stroke-dasharray: 502.65; stroke-dashoffset: 502.65;"/>
            </svg>
            <div class="progress-ring-text" id="progress-text">0%</div>
            <div class="progress-ring-label">Daily Goal</div>
        `;
        this.container?.appendChild(ringDiv);
    }

    /**
     * Render badges
     */
    renderBadges() {
        const badgesDiv = document.createElement('div');
        badgesDiv.className = 'gamified-card';
        badgesDiv.innerHTML = '<h3 style="margin-top: 0;">🏅 Achievements</h3>';

        const badgeContainer = document.createElement('div');
        badgeContainer.className = 'badge-container';
        badgeContainer.id = 'badges-container';

        Object.entries(this.engine.badges).forEach(([key, badge]) => {
            const badgeEl = document.createElement('div');
            badgeEl.className = `achievement-badge ${badge.unlocked ? 'unlocked' : 'locked'}`;
            badgeEl.id = `badge-${key}`;
            badgeEl.title = badge.description;
            badgeEl.innerHTML = `
                <div class="badge-icon">${badge.icon}</div>
                <div class="badge-name">${badge.name}</div>
            `;
            badgeContainer.appendChild(badgeEl);
        });

        badgesDiv.appendChild(badgeContainer);
        this.container?.appendChild(badgesDiv);
    }

    /**
     * Render streak counter
     */
    renderStreak() {
        const streakDiv = document.createElement('div');
        streakDiv.className = 'streak-container';
        streakDiv.id = 'streak-container';
        streakDiv.innerHTML = `
            <div class="streak-icon">🔥</div>
            <div class="streak-text">
                <div class="streak-number" id="streak-number">${this.engine.streak}</div>
                <div class="streak-label">Current Streak</div>
            </div>
        `;
        this.container?.appendChild(streakDiv);
    }

    /**
     * Render stats
     */
    renderStats() {
        const stats = this.engine.getSessionStats();
        const statsDiv = document.createElement('div');
        statsDiv.className = 'gamified-card';
        statsDiv.innerHTML = `
            <h3 style="margin-top: 0;">📊 Session Stats</h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Duration</div>
                    <div class="stat-value" id="stat-duration">${stats.duration}s</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Reps/Min</div>
                    <div class="stat-value" id="stat-rpm">${stats.repsPerMinute}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Form Score</div>
                    <div class="stat-value" id="stat-form">${stats.formScore}%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Daily Goal</div>
                    <div class="stat-value" id="stat-daily">${Math.round(stats.dailyProgress * 100)}%</div>
                </div>
            </div>
        `;
        this.container?.appendChild(statsDiv);
    }

    /**
     * Update rep counter display with animation
     */
    updateRepCounter(repCount, motivationalMsg) {
        const counter = document.getElementById('rep-counter');
        if (counter) {
            counter.textContent = repCount;
            counter.classList.add('pulse');
            setTimeout(() => counter.classList.remove('pulse'), 600);
        }

        const msgEl = document.getElementById('motivational-msg');
        if (msgEl) {
            msgEl.textContent = motivationalMsg;
        }
    }

    /**
     * Update progress ring
     */
    updateProgressRing(progress) {
        const circle = document.getElementById('progress-circle');
        const text = document.getElementById('progress-text');

        if (circle && text) {
            const circumference = 2 * Math.PI * 80;
            const offset = circumference * (1 - progress);
            circle.style.strokeDashoffset = offset;
            text.textContent = `${Math.round(progress * 100)}%`;
        }
    }

    /**
     * Unlock badge in UI
     */
    unlockBadgeUI(badgeKey) {
        const badgeEl = document.getElementById(`badge-${badgeKey}`);
        if (badgeEl) {
            badgeEl.classList.remove('locked');
            badgeEl.classList.add('unlocked');
        }
    }

    /**
     * Update streak display
     */
    updateStreak(streak) {
        const streakNum = document.getElementById('streak-number');
        if (streakNum) {
            streakNum.textContent = streak;
        }
    }

    /**
     * Update stats display
     */
    updateStats(stats) {
        const duration = document.getElementById('stat-duration');
        const rpm = document.getElementById('stat-rpm');
        const form = document.getElementById('stat-form');
        const daily = document.getElementById('stat-daily');

        if (duration) duration.textContent = `${stats.duration}s`;
        if (rpm) rpm.textContent = stats.repsPerMinute;
        if (form) form.textContent = `${stats.formScore}%`;
        if (daily) daily.textContent = `${Math.round(stats.dailyProgress * 100)}%`;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GamificationEngine, GamificationUI };
}
