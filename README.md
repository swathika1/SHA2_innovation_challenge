# SHA2_innonvation_challenge
IC 2026 


Multimodal Home Rehab Form Coach (MSK / Post-op Rehab)
Short Description / Features (Pointers):
Target: Outpatient/post-op/MSK patients needing rehab


Detects exercises → counts reps/sets, checks form quality, flags mistakes


Real-time guidance: “knees tracking inward”, “slow down”, “stand taller”


Generates clinician-ready summary: adherence %, quality trend, top errors, “needs intervention” flags


Multimodal inputs:


Video → pose/joint angles (primary, MediaPipe / MoveNet)


Audio → optional effort/pain check


Patient-reported → pain/perceived exertion


Optional wearable → smoothness, stability


MVP → on-device pose extraction + rule-based checks + PDF summary


Advanced → small temporal ML (1D-CNN / LSTM) to predict quality score


Personalized feedback → baseline range-of-motion, progressive targets


Multi-lingual cues → SEA-LION can give audio/text instructions in different languages
