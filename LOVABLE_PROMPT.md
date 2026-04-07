# REHAB MOBILE APP - COMPLETE UI/UX BUILD SPECIFICATION

**Platform:** React Native / Flutter / Capacitor-based mobile app  
**Target:** iOS + Android (responsive, touch-optimized)  
**Key User:** Elderly patients (Lim Ah Mei, 68-year-old, post-op knee surgery)

---

## 1. ONBOARDING FLOW (3-SCREEN CAROUSEL)

### Screen 1: Welcome
- **Background Gradient:** Pastel blue → purple (#e0e7ff → #e879f9)
- **Icon:** Person walking 🧍‍♀️ (FontAwesome fa-person-walking, 80px, primary color)
- **Heading:** "Welcome to your Rehab Companion 💙"
- **Subheading:** "Helping you recover safely at home"
- **Typography:** Bold, friendly, large (24px heading, 16px body)
- **Button:** "Next" (bottom, full-width, blue primary)
- **Pagination:** 3 dots, first active (●●○)

### Screen 2: Smart AI Posture
- **Background Gradient:** Pastel orange → pink (#ffedd5 → #fbcfe8)
- **Icon:** Robot 🤖 (FontAwesome fa-robot, 80px, purple #d946ef)
- **Heading:** "Smart posture correction with AI 🤖"
- **Subheading:** "Real-time guidance to ensure you move correctly"
- **Button:** "Next"
- **Pagination:** (○●○)

### Screen 3: Progress Tracking
- **Background Gradient:** Pastel green → blue (#dcfce7 → #bfdbfe)
- **Icon:** Chart line 📈 (FontAwesome fa-chart-line, 80px, success color #059669)
- **Heading:** "Track your progress, stay strong 💪"
- **Subheading:** "Monitor your daily streaks and stick to the plan"
- **Button:** "Get Started" (ONLY on this screen—leads to login)
- **Pagination:** (○○●)

**Transitions:** Smooth horizontal swipe, fade between slides  
**Functionality:** Tap "Next" OR swipe left to advance

---

## 2. LOGIN SCREEN

**Layout:** Single centered form

### Elements (in order):
1. **Shield Icon** (FontAwesome fa-shield-alt, 60px, primary blue)
2. **Heading:** "Sign In" (28px, bold, dark)
3. **NRIC/FIN Input**
   - Placeholder: "NRIC / FIN"
   - Rounded corners: 16px
   - Border: 2px solid #e2e8f0
   - Background: #f8fafc
   - Padding: 20px
   - Font size: 18px
   - Margin bottom: 20px

4. **Password Input**
   - Placeholder: "Password"
   - Type: password (dots/asterisks)
   - Same styling as NRIC input
   - Margin bottom: 30px

5. **Log In Button**
   - Background: Linear gradient blue (#4F8EF7 → #357EE8)
   - Color: White
   - Padding: 20px
   - Border radius: 16px
   - Font size: 18px, bold
   - Full width
   - Box shadow: soft blue glow

**IMPORTANT:** 
- NO dropdown showing "Patient (Lim Ah Mei)"
- NO role selector visible
- Backend can handle role as fixed "patient" if needed
- Store NRIC in localStorage/state for profile display

---

## 3. DASHBOARD SCREEN

### Header:
- **Avatar:** Profile image (placeholder or Lim Ah Mei's image)
- **Greeting:** "Hi, Lim Ah Mei"
- **Streak Badge:** Fire icon 🔥 "5 Day Streak"
- **Settings Icon:** (top right, links to profile)

### Main Cards (2 columns or stacked):

#### Card 1: "Start Exercise"
- **Icon:** Running figure (blue background)
- **Title:** "Start Exercise"
- **Description:** "Begin your rehab session"
- **Arrow:** Right chevron
- **Action:** Tap → opens exercise camera screen

#### Card 2: "Talk to Jimmy"
- **Icon:** Microphone (purple background)
- **Title:** "Talk to Jimmy"
- **Description:** "Voice assistant for guidance"
- **Arrow:** Right chevron
- **Action:** Tap → opens Jimmy voice screen

### Upcoming Sessions Section:
- Title: "Upcoming Sessions"
- Show 2-3 mock appointments (calendar icon, doctor name, date/time)

### Notifications Section:
- Medication reminders, check-ins

### Navigation (Bottom Tab Bar):
- **Home** (filled)
- **Plan** (dumbbell icon)
- **MICROPHONE** (Center, larger purple circle button with glow)
- **Profile** (user icon)

---

## 4. PROFILE SCREEN

### Header:
- Back arrow
- "Profile" title
- 24px padding

### Profile Header Section:
- **Avatar:** Elderly Asian/Singaporean woman, rounded, 100px diameter, subtle border/shadow
- **Name:** "Lim Ah Mei" (standing bold, 26px)
- **Age/Gender:** "Female, 68 Years Old" (14px, gray)
- **NRIC Badge:** 
  - Dynamic display: "NRIC: S32580" (entered at login)
  - Background: Blue (#4F8EF7)
  - Color: White
  - Padding: 4px 12px
  - Border radius: 12px
  - Font: Bold, 14px
  - Margin top: 5px
- **Condition:** "Post-Op Knee Surgery"

### Action Buttons:
- **Call Caregiver:** Orange background (#FF8A3D), blue icon
- **Call Doctor:** Red background (#EF4444), blue icon
- Both buttons: Side by side, flex layout, 12px gap

### Progress Overview Card:
- **Title:** "PROGRESS OVERVIEW" (12px, uppercase, gray, bold)
- **Two metrics side-by-side:**
  - "85%" (26px, bold, green #10b981) above "Rehab Complete" (12px, gray)
  - "92%" (26px, bold, purple #7B61FF) above "Adherence" (12px, gray)
- Background: Light gray (#f8fafc)
- Padding: 20px
- Border radius: 16px

### Medical History Card:
- **Title:** "MEDICAL HISTORY" (12px, uppercase, gray)
- **Icon:** Clipboard (primary color)
- **Conditions as pills/chips:**
  - "Knee osteoarthritis"
  - "Hypertension"
  - "Diabetes Type 2" (if applicable)
  - Light blue background, dark text, 8px padding

### Surgeries Card:
- **Title:** "SURGERIES" (12px, uppercase, gray)
- **Icon:** Surgical mask or scalpel
- List: "Total ACL Knee Replacement" + date

### Medications Card:
- **Title:** "MEDICATIONS" (12px, uppercase, gray)
- **Icon:** Pill bottle
- List with dosage info

### Allergies Card:
- **Title:** "ALLERGIES" (12px, uppercase, gray)
- **Icon:** Warning symbol
- List: "Penicillin" (if applicable)

**Card Styling (all sections):**
- Border radius: 16px
- Padding: 20px
- Background: White with subtle border (#e2e8f0)
- Box shadow: 0 4px 15px rgba(0,0,0,0.05)
- Margin bottom: 16px

---

## 5. JIMMY VOICE ASSISTANT SCREEN

### Layout:
- **Back button** (top left)
- **Language selector** (top right)
  - Dropdown: English / 中文 (Mandarin) / தமிழ் (Tamil) / Melayu (Malay)

### Center Avatar Container:
- **Circular avatar:** "JI" initials in blue circle, 150px diameter
- Waveform bars below avatar (5 bars, animating when listening/speaking)

### Text Display:
- **Greeting text:** "Aah Mee, how can I help you today?" (centered, 18px, friendly)
- **Response text:** Displayed below greeting (dynamic, italicized)

### Microphone Button:
- **Size:** 90px circular
- **Color:** Purple (#7B61FF)
- **Icon:** Microphone (FontAwesome fa-microphone, white, 40px)
- **Glow effect:** Soft drop-shadow when active
- **Position:** Centered horizontally, slightly above bottom safe area
- **Pressed state:** Scale down slightly, brighter glow
- **Tap behavior:**
  - Tap → Listen for user voice
  - Display: "Listening..." text
  - Waveform bars animate
  - After detection → Send to LLM
  - Receive response
  - **CRITICAL: SPEAK response using Web Speech API:**
    ```javascript
    const utterance = new SpeechSynthesisUtterance(responseText);
    const langMap = {
      'en': 'en-US',
      'zh': 'zh-CN',
      'ta': 'ta-IN',
      'ms': 'ms-MY'
    };
    utterance.lang = langMap[selectedLanguage] || 'en-US';
    utterance.rate = 0.95;
    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
    ```

### Requirements:
- MUST play audio response (not just show text)
- Voice must match language selector
- Smooth animations during listening/speaking
- Visual feedback (waveform, color changes)

---

## 6. EXERCISE CAMERA SCREEN

### Layout:
- **Back button** (top left)
- **Exercise name** (e.g., "Lateral Trunk Tilt")
- **Live camera feed** (full screen, portrait)

### Camera Requirements:
- **getUserMedia constraints:**
  ```javascript
  {
    video: {
      facingMode: "user",
      width: { ideal: 640 },
      height: { ideal: 480 },
      aspectRatio: 4/3
    }
  }
  ```
- **NO zoom distortion**
- **Skeleton overlay** on top of video (canvas, absolute positioned)
  - Draw MediaPipe landmarks OR simulate stick figure
  - Update every frame
  - Visible and centered

### Status Badge:
- Top right corner
- Green "✓ Good Posture" OR Yellow "⚠ Keep back straight"
- Contextual feedback

### Rep Counter:
- Large number display (current rep count)
- Increments during exercise

### Controls:
- **Start/Stop button:** RED when recording, GREEN when ready
- Text: "START" or "STOP"

---

## 7. GLOBAL UI THEME & STYLING

### Color Palette:
```
Primary Blue:       #4F8EF7
Secondary Purple:   #7B61FF
Accent Orange:      #FF8A3D
Success Green:      #10b981
Warning Yellow:     #f59e0b
Danger Red:         #ef4444
Dark Text:          #1e293b
Light Gray:         #64748b
Border Gray:        #e2e8f0
Background Light:   #f8fafc
White:              #ffffff
```

### Typography:
- **Font:** Inter (or system sans-serif)
- **Heading 1:** 28px, bold, #1e293b
- **Heading 2:** 24px, bold, #1e293b
- **Heading 3:** 20px, semi-bold, #1e293b
- **Body:** 16px, regular, #1e293b
- **Small text:** 14px, regular, #64748b
- **Labels:** 12px, uppercase, bold, #64748b

### Spacing:
- **Padding:** 16px–20px inside cards/containers
- **Margin between sections:** 20px
- **Gap between buttons:** 12px
- **Tab bar safe area:** 16px from bottom

### Borders & Shadows:
- **Border radius:** 16px (cards), 12px (buttons), 8px (inputs)
- **Input border:** 2px solid #e2e8f0
- **Card shadow:** `0 4px 15px rgba(0,0,0,0.05)`
- **Button shadow (hover):** `0 8px 25px rgba(0,0,0,0.15)`
- **Soft focus:** Subtle blur when modals appear

### Button Styling:
- **Primary buttons:** Blue background (#4F8EF7), white text, 16px radius, 20px padding
- **Secondary buttons:** Purple outline, purple text, transparent background
- **Accent buttons:** Orange (#FF8A3D)
- **Danger buttons:** Red (#ef4444)
- All buttons: Minimum 48px touch target

---

## 8. ONBOARDING → LOGIN → DASHBOARD FLOW

```
Splash Screen / Onboarding 3-Pager
    ↓ (Get Started)
Login Screen (NRIC + Password)
    ↓ (Log In)
Dashboard (with user greeting)
    ↓ (Profile icon)
Profile Screen (show NRIC dynamically)
```

---

## 9. MOBILE OPTIMIZATION

- **Safe area handling:** Account for notches/rounded corners
- **Touch targets:** Min 48x48px
- **Responsive:** Works on 375px (iPhone SE) to 1080px (tablets)
- **Orientation:** Portrait primary, landscape supported
- **Accessibility:** High contrast, labeled buttons, keyboard navigation

---

## 10. PERFORMANCE

- **Lazy load:** Images, exercise videos
- **Cache:** Store profile data locally
- **Smooth animations:** 60fps transitions
- **Offline mode:** Show cached data if no connection

---

## 11. FINAL CHECKLIST

- [ ] Onboarding carousel with 3 screens + pagination dots
- [ ] Next buttons flow correctly (Next → Next → Get Started)
- [ ] Login shows ONLY NRIC + Password (NO patient name dropdown)
- [ ] NRIC input stored in state and displayed on profile
- [ ] Profile shows elderly woman avatar (rounded, 100px)
- [ ] Medical history in card-based layout with icons
- [ ] Microphone button centered with glow effect
- [ ] Jimmy SPEAKS responses (Web Speech API implemented)
- [ ] Camera feed with 4/3 aspect ratio (NO zoom distortion)
- [ ] Skeleton overlay visible on camera
- [ ] Button colors consistent across app
- [ ] All cards have 16px radius, proper shadows
- [ ] Padding/spacing consistent (16–20px)
- [ ] Language selector on Jimmy screen works
- [ ] Entire app uses Inter font
- [ ] Tab navigation works smoothly

---

**That's your complete spec.** Take this to Lovable, Claude, or any AI and it will build you exactly what you need.
