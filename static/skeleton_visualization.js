/**
 * MediaPipe Skeleton Visualization
 * Displays 33 pose landmarks in real-time with proper coloring
 */

class SkeletonVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.landmarks = null;
        
        // Color scheme for different body parts
        this.colors = {
            head: '#0099FF',      // Blue
            torso: '#00CC00',     // Green
            leftArm: '#FFFF00',   // Yellow
            rightArm: '#FFFF00',  // Yellow
            leftLeg: '#FF0000',   // Red
            rightLeg: '#FF0000',  // Red
            joints: '#FFFFFF',    // White for joints
        };
        
        // MediaPipe landmark indices
        this.landmarks_map = {
            // Head (0-10)
            nose: 0,
            leftEye: 1, rightEye: 2,
            leftEar: 3, rightEar: 4,
            leftShoulder: 11, rightShoulder: 12,
            
            // Torso (11-12, 23-24)
            
            // Left arm (13-15)
            leftElbow: 13, leftWrist: 15,
            // Right arm (14-16)
            rightElbow: 14, rightWrist: 16,
            
            // Left leg (25-27)
            leftKnee: 25, leftAnkle: 27,
            // Right leg (26-28)
            rightKnee: 26, rightAnkle: 28,
            
            // Hips (23-24)
            leftHip: 23, rightHip: 24,
        };
        
        // Connections between landmarks (skeleton)
        this.connections = [
            // Head
            [0, 1], [0, 2], [1, 3], [2, 4], [3, 0], [4, 0],
            // Torso
            [11, 12], [11, 23], [12, 24], [23, 24],
            // Left arm
            [11, 13], [13, 15],
            // Right arm
            [12, 14], [14, 16],
            // Left leg
            [23, 25], [25, 27],
            // Right leg
            [24, 26], [26, 28],
            // Face contour (optional, minimal)
            [1, 2], [3, 4]
        ];
        
        // Joint radius
        this.jointRadius = 4;
        this.connectionWidth = 2;
    }
    
    getPartColor(landmarkIndex) {
        /**
         * Determine color based on landmark index
         * 0-10: Head (blue)
         * 11-16: Arms (yellow)
         * 17-22: Hands (yellow) 
         * 23-28: Torso & Legs (green/red)
         */
        if (landmarkIndex <= 10) {
            return this.colors.head;  // Blue
        } else if (landmarkIndex <= 16) {
            return this.colors.leftArm;  // Yellow (arms)
        } else if (landmarkIndex <= 22) {
            return this.colors.leftArm;  // Yellow (hands)
        } else if (landmarkIndex <= 24) {
            return this.colors.torso;  // Green (hips)
        } else if (landmarkIndex % 2 === 0) {
            return this.colors.rightLeg;  // Red (right leg)
        } else {
            return this.colors.leftLeg;  // Red (left leg)
        }
    }
    
    draw(landmarks) {
        /**
         * Draw skeleton visualization
         * @param landmarks: Array of [x, y, z] for 33 MediaPipe landmarks
         */
        if (!landmarks || landmarks.length < 33) {
            return;
        }
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Normalize landmarks to canvas size
        const normalizedLandmarks = this.normalizeLandmarks(landmarks);
        
        // Draw connections first (so they appear behind points)
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        this.ctx.lineWidth = this.connectionWidth;
        
        for (let [start, end] of this.connections) {
            if (start < normalizedLandmarks.length && end < normalizedLandmarks.length) {
                const p1 = normalizedLandmarks[start];
                const p2 = normalizedLandmarks[end];
                
                // Only draw if both points have good confidence
                if (p1[2] > 0.3 && p2[2] > 0.3) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(p1[0], p1[1]);
                    this.ctx.lineTo(p2[0], p2[1]);
                    this.ctx.stroke();
                }
            }
        }
        
        // Draw landmarks (joints)
        for (let i = 0; i < normalizedLandmarks.length; i++) {
            const [x, y, confidence] = normalizedLandmarks[i];
            
            // Only draw if confidence is sufficient
            if (confidence > 0.3) {
                const color = this.getPartColor(i);
                
                // Draw circle
                this.ctx.fillStyle = color;
                this.ctx.beginPath();
                this.ctx.arc(x, y, this.jointRadius, 0, 2 * Math.PI);
                this.ctx.fill();
                
                // Draw border
                this.ctx.strokeStyle = this.colors.joints;
                this.ctx.lineWidth = 1;
                this.ctx.stroke();
            }
        }
        
        this.landmarks = landmarks;
    }
    
    normalizeLandmarks(landmarks) {
        /**
         * Normalize landmarks to canvas coordinates
         * Input: landmarks in normalized coords (0-1) or pixel coords
         * Output: landmarks in canvas pixel coords
         */
        const normalized = [];
        
        for (let i = 0; i < landmarks.length; i++) {
            const [x, y, z] = landmarks[i];
            
            // Check if already normalized (0-1) or in pixels
            let canvasX, canvasY;
            
            if (x > 1.5) {
                // Likely pixel coordinates, normalize first
                canvasX = x / 720 * this.canvas.width;  // Assume 720px width
                canvasY = y / 1280 * this.canvas.height;  // Assume 1280px height
            } else {
                // Already normalized
                canvasX = x * this.canvas.width;
                canvasY = y * this.canvas.height;
            }
            
            normalized.push([canvasX, canvasY, z]);
        }
        
        return normalized;
    }
    
    drawDebugInfo(exerciseName, reps) {
        /**
         * Draw debug information overlay
         */
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        this.ctx.fillRect(10, 10, 300, 80);
        
        this.ctx.fillStyle = '#00FF00';
        this.ctx.font = 'bold 16px Arial';
        this.ctx.fillText(`Exercise: ${exerciseName}`, 20, 35);
        this.ctx.fillText(`Reps: ${reps}`, 20, 60);
        this.ctx.fillText(`Landmarks: ${this.landmarks ? this.landmarks.length : 0}`, 20, 85);
    }
    
    getConfiguration() {
        /**
         * Get visualization configuration
         */
        return {
            jointRadius: this.jointRadius,
            connectionWidth: this.connectionWidth,
            landmarkCount: 33,
            connections: this.connections.length,
        };
    }
}

// Export for use in session.html
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SkeletonVisualizer;
}
