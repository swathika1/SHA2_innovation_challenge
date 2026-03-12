"""
meralion_avatar.py - AI Avatar "Jimmy" powered by Meralion
Handles patient interactions regarding FAQs, exercises, and performance.
Integrates with RAG databases and patient performance history.
"""

import requests
from typing import Dict, List, Optional, Tuple
from config import MERILION_USERNAME, MERILION_API_KEY, MERILION_BASE_URL
from database import query_db


class AvatarJimmy:
    """AI Avatar powered by Meralion for patient interaction"""
    
    def __init__(self):
        """Initialize avatar with Meralion credentials"""
        self.username = MERILION_USERNAME
        self.api_key = MERILION_API_KEY
        self.base_url = MERILION_BASE_URL
        self.avatar_name = "Jimmy"
        self.system_prompt = """You are Jimmy, a friendly and knowledgeable rehabilitation coach avatar for the Home Rehab Coach app.
Your role is to help patients with:
1. Exercise FAQs and how to perform exercises correctly
2. Performance feedback and motivation based on their session history
3. General rehabilitation guidance and appointment questions
4. Understanding their progress, scores, pain levels, and adherence

Guidelines:
- Be encouraging and empathetic
- Use simple, clear language
- Reference specific patient data when relevant (e.g., "I see you scored 85% last session!")
- NEVER provide medical diagnosis - suggest consulting their doctor for serious concerns
- Respond in the same language the patient uses
- Keep responses concise (2-4 sentences) and actionable

Available Data:
- Patient profiles, exercises, sessions with quality scores (0-100) and pain (0-10)
- KIMORE exercises: Lifting Arms, Lateral Trunk Tilt, Trunk Rotation, Squat, Trunk Rotation+Target (scored 0-50)
- KERAAL exercises: Forward Flexion (CTK), Flank Stretch (ELK), Torso Rotation (RTK) (scored 0-50, ≥27.5=correct form)
- Appointments, clinician notes, caregiver information
- Real-time webcam scoring (OpenPose/BlazePose), pain tracking, adherence/streak tracking
- Multilingual support: English, Chinese, Malay, Tamil, Singlish"""

    def _build_headers(self) -> Dict:
        """Build authentication headers for Meralion API"""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    def get_patient_context(self, patient_id: int) -> str:
        """
        Get comprehensive patient context from database.
        Includes profile, condition, exercises, sessions, appointments, notes, caregiver info.
        """
        try:
            # Get patient info
            patient = query_db(
                '''SELECT u.name, u.email, p.condition, p.surgery_date, p.current_week,
                          p.avg_quality_score, p.avg_pain_level, p.adherence_rate,
                          p.completed_sessions, p.streak_days
                   FROM patients p JOIN users u ON p.user_id = u.id WHERE p.user_id = ?''',
                (patient_id,),
                one=True
            )
            
            if not patient:
                return "Patient profile not yet created."
            
            # Get recent sessions summary
            recent_sessions = query_db('''
                SELECT COUNT(*) as total_sessions, 
                       AVG(quality_score) as avg_score,
                       AVG(pain_after - pain_before) as pain_improvement
                FROM sessions
                WHERE patient_id = ? AND completed_at IS NOT NULL
            ''', (patient_id,), one=True)
            
            # Get current exercises with full details
            exercises = query_db('''
                SELECT e.name, e.category, w.sets, w.reps, w.frequency, w.instructions
                FROM workouts w
                JOIN exercises e ON w.exercise_id = e.id
                WHERE w.patient_id = ? AND w.is_active = 1
                LIMIT 10
            ''', (patient_id,))
            
            context = f"""Patient: {patient['name']}
Condition: {patient['condition']}
Surgery Date: {patient['surgery_date'] or 'N/A'}
Current Rehab Week: {patient['current_week']}
Sessions Completed: {patient['completed_sessions'] or (recent_sessions['total_sessions'] if recent_sessions else 0)}
Streak Days: {patient['streak_days'] or 0}
Adherence Rate: {patient['adherence_rate']:.1f}%
Average Quality Score: {patient['avg_quality_score']:.1f}/100
Average Pain Level: {patient['avg_pain_level']:.1f}/10"""
            
            if exercises:
                context += "\n\nActive Exercise Plan:"
                for ex in exercises:
                    context += f"\n- {ex['name']} ({ex['category'] or 'general'}): {ex['sets']}x{ex['reps']} {ex['frequency']}"
                    if ex['instructions']:
                        context += f" — {ex['instructions']}"
            else:
                context += "\nCurrent Exercises: No exercises assigned yet"

            # Recent session details (compact — 4 most recent)
            recent_detail = query_db('''
                SELECT s.quality_score, s.pain_before, s.pain_after, s.completed_at
                FROM sessions s
                WHERE s.patient_id = ? AND s.completed_at IS NOT NULL
                ORDER BY s.completed_at DESC LIMIT 4
            ''', (patient_id,))
            if recent_detail:
                context += "\n\nRecent Sessions:"
                for s in recent_detail:
                    context += f"\n- Q:{s['quality_score']}, Pain:{s['pain_before']}->{s['pain_after']} ({s['completed_at']})"

            # Upcoming appointments
            appointments = query_db('''
                SELECT a.appointment_date, a.appointment_time, a.status, u.name as doctor_name
                FROM appointments a JOIN users u ON a.doctor_id = u.id
                WHERE a.patient_id = ? AND a.status = 'scheduled'
                ORDER BY a.appointment_date ASC LIMIT 3
            ''', (patient_id,))
            if appointments:
                context += "\n\nUpcoming Appointments:"
                for a in appointments:
                    context += f"\n- {a['appointment_date']} {a['appointment_time']} with Dr. {a['doctor_name']}"

            # Clinician notes
            notes = query_db('''
                SELECT cn.note_text, cn.created_at, u.name as doctor_name
                FROM clinician_notes cn JOIN users u ON cn.doctor_id = u.id
                WHERE cn.patient_id = ? ORDER BY cn.created_at DESC LIMIT 3
            ''', (patient_id,))
            if notes:
                context += "\n\nRecent Clinician Notes:"
                for n in notes:
                    context += f"\n- Dr. {n['doctor_name']} ({n['created_at']}): {n['note_text'][:200]}"

            # Assigned doctor
            doctor = query_db('''
                SELECT u.name FROM doctor_patient dp
                JOIN users u ON dp.doctor_id = u.id WHERE dp.patient_id = ?
            ''', (patient_id,))
            if doctor:
                context += "\nAssigned Doctor(s): " + ", ".join([d['name'] for d in doctor])

            # Caregiver info
            caregiver = query_db('''
                SELECT u.name, cp.relationship FROM caregiver_patient cp
                JOIN users u ON cp.caregiver_id = u.id WHERE cp.patient_id = ?
            ''', (patient_id,))
            if caregiver:
                context += "\nCaregiver(s): " + ", ".join([f"{c['name']} ({c['relationship']})" for c in caregiver])
            
            return context
        except Exception as e:
            return f"Could not retrieve patient context: {str(e)}"

    def get_rag_context(self, query: str, top_k: int = 3) -> str:
        """
        Retrieve relevant information from RAG databases.
        Includes exercise guides, FAQs, and rehabilitation knowledge.
        """
        try:
            from rag_engine import retrieve
            results = retrieve(query, top_k=top_k)
            
            if not results:
                return ""
            
            context_parts = []
            for result in results:
                context_parts.append(result.get('text', ''))
            
            return "\n---\n".join(context_parts)
        except Exception as e:
            print(f"[AVATAR] RAG retrieval failed: {e}")
            return ""

    def get_performance_summary(self, patient_id: int) -> str:
        """
        Get concise performance summary from recent sessions.
        Keeps output compact so the MERaLiON instruction stays within token limits.
        """
        try:
            # Get last 5 sessions only — keeps payload manageable
            sessions = query_db('''
                SELECT id, quality_score, pain_before, pain_after, effort_level,
                       completed_perc, completed_at
                FROM sessions
                WHERE patient_id = ? AND completed_at IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 5
            ''', (patient_id,))
            
            if not sessions:
                return "No session data available yet."
            
            sessions = list(sessions)
            avg_quality = sum(s['quality_score'] or 0 for s in sessions) / len(sessions)
            avg_pain_improvement = sum(
                (s['pain_before'] or 0) - (s['pain_after'] or 0) 
                for s in sessions
            ) / len(sessions)
            
            latest = sessions[0]
            
            summary = f"""Performance ({len(sessions)} recent sessions):
Latest: {latest['quality_score']}% quality, {latest['completed_perc'] or 0}% complete, pain {latest['pain_before']}->{latest['pain_after']}
Average quality: {avg_quality:.0f}%, Avg pain improvement: {avg_pain_improvement:.1f} pts"""
            
            # Per-session one-liner
            for sess in sessions:
                # Get exercise names for this session
                sess_exercises = query_db('''
                    SELECT exercise_name, quality_score
                    FROM session_exercises WHERE session_id = ?
                ''', (sess['id'],))
                ex_parts = []
                if sess_exercises:
                    for se in sess_exercises:
                        ex_name = se['exercise_name'] or 'exercise'
                        ex_parts.append(f"{ex_name}:{se['quality_score'] or '?'}")
                ex_str = ", ".join(ex_parts) if ex_parts else "no exercises logged"
                summary += f"\n  {sess['completed_at']}: Q{sess['quality_score']}, pain {sess['pain_before']}->{sess['pain_after']}, [{ex_str}]"
            
            return summary
        except Exception as e:
            print(f"[AVATAR] Performance summary failed: {e}")
            return "Could not retrieve performance data."

    def query_jimmy(
        self,
        patient_id: int,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        include_rag: bool = True,
        include_performance: bool = True,
        preferred_language: str = "English"
    ) -> str:
        """
        Query Jimmy (Meralion) with patient context, RAG, and performance data.
        
        Args:
            patient_id: User/patient ID
            user_message: The patient's question/request
            conversation_history: List of previous messages [{"role": "user"/"assistant", "content": "..."}]
            include_rag: Include RAG retrieval context
            include_performance: Include detailed performance summary
        
        Returns:
            Jimmy's response text
        """
        try:
            # Build context
            patient_context = self.get_patient_context(patient_id)
            rag_context = self.get_rag_context(user_message) if include_rag else ""
            performance_context = self.get_performance_summary(patient_id) if include_performance else ""
            
            # Build instruction for Meralion
            language_rules = {
                "English": "Respond fully in clear English.",
                "Chinese": "Respond fully in Simplified Chinese (中文).",
                "Malay": "Respond fully in Bahasa Melayu.",
                "Tamil": "Respond fully in Tamil (தமிழ்).",
                "Singlish": "Respond in Singapore colloquial English (Singlish), friendly and natural, while staying clear and safe."
            }

            selected_language = preferred_language if preferred_language in language_rules else "English"

            # ── Build instruction — USER QUESTION FIRST so it's never truncated ──
            instruction_parts = [
                self.system_prompt,
                "",
                "Language Instruction:",
                language_rules[selected_language],
            ]

            # Add conversation history BEFORE context (keeps flow natural)
            if conversation_history:
                instruction_parts.append("\nRecent Conversation:")
                for msg in conversation_history[-4:]:
                    role = "Patient" if msg['role'] == 'user' else "Jimmy"
                    instruction_parts.append(f"{role}: {msg['content']}")

            # Patient info + performance (concise)
            instruction_parts.extend(["", "Patient Info:", patient_context])
            if performance_context:
                instruction_parts.extend(["", "Performance:", performance_context])

            # RAG knowledge (trimmed)
            if rag_context:
                trimmed_rag = rag_context[:1500]  # Cap RAG at 1500 chars
                instruction_parts.extend(["", "Relevant Knowledge:", trimmed_rag])

            # The actual question — ALWAYS last and clearly marked
            instruction_parts.extend([
                "",
                "=== ANSWER THE FOLLOWING QUESTION ===",
                f"Patient: {user_message}",
                "Jimmy:"
            ])

            full_instruction = "\n".join(instruction_parts)

            # Hard-cap at 6000 chars — trim MIDDLE context, keep start (system) + end (question)
            MAX_INSTRUCTION = 6000
            if len(full_instruction) > MAX_INSTRUCTION:
                # Keep first 2500 chars (system prompt + language) and last 2000 chars (question + recent context)
                original_len = len(full_instruction)
                head = full_instruction[:2500]
                tail = full_instruction[-(MAX_INSTRUCTION - 2600):]
                full_instruction = head + "\n... (context trimmed) ...\n" + tail
                print(f"[AVATAR] ⚠️  Instruction trimmed from {original_len} to {len(full_instruction)} chars")

            print(f"[AVATAR] Instruction length: {len(full_instruction)} chars")

            payload = {
                "instruction": full_instruction,
                "question": "answer"
            }
            
            headers = self._build_headers()
            
            response = requests.post(
                f"{self.base_url}/chat",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            # Extract response
            data = response.json()
            if "response" in data:
                if isinstance(data["response"], dict):
                    return data["response"].get("text", str(data["response"]))
                return str(data["response"])
            
            return "I'm having trouble understanding. Could you rephrase that?"
        
        except requests.exceptions.Timeout:
            return "Sorry, the request timed out. Please try again."
        except requests.exceptions.RequestException as e:
            print(f"[AVATAR] Meralion query failed: {e}")
            return "I'm experiencing technical difficulties. Please try again later."
        except Exception as e:
            print(f"[AVATAR] Unexpected error: {e}")
            return "Something went wrong. Please try again."

    def get_avatar_intro(self, patient_id: int) -> str:
        """Get a personalized introduction from Jimmy"""
        try:
            patient = query_db(
                'SELECT u.name FROM patients p JOIN users u ON p.user_id = u.id WHERE p.user_id = ?',
                (patient_id,),
                one=True
            )
            
            if not patient:
                intro_message = "Hi! I'm Jimmy, your rehabilitation coach. How can I help you today?"
            else:
                intro_message = f"Hi {patient['name']}! I'm Jimmy, your rehabilitation coach. I'm here to help you with exercise guidance, FAQs, and feedback on your progress. What would you like to know?"
            
            return intro_message
        except Exception as e:
            print(f"[AVATAR] Could not generate intro: {e}")
            return "Hi! I'm Jimmy, your rehabilitation coach. How can I help you today?"


# Singleton instance
_avatar_instance = None


def get_avatar() -> AvatarJimmy:
    """Get or create avatar singleton instance"""
    global _avatar_instance
    if _avatar_instance is None:
        _avatar_instance = AvatarJimmy()
    return _avatar_instance


def test_avatar_connection() -> Dict:
    """Test avatar connectivity"""
    avatar = get_avatar()
    try:
        response = avatar.query_jimmy(
            patient_id=1,
            user_message="Hello, can you help me with my rehabilitation exercises?",
            include_rag=False,
            include_performance=False
        )
        return {
            "ok": bool(response),
            "message": response[:100]
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }


if __name__ == "__main__":
    print("Testing Avatar Jimmy...")
    result = test_avatar_connection()
    print(f"Status: {result}")
