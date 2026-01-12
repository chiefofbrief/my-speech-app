import streamlit as st
import openai
import json
import os
import re
import random
from audio_recorder_streamlit import audio_recorder

# ---------------- CONFIG ----------------
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=api_key)

MAX_ATTEMPTS = 3
MAX_WHO_ELSE = 2  # Only ask "who else?" twice per photo
TTS_SPEED = 0.75  # Slower for more natural pace

# ---------------- HELPERS ----------------
def slow_opening(text):
    """Extra slow word-by-word pacing for opening lines."""
    return "\n\n".join(text.split())

def add_pauses(text):
    """Add longer pauses between sentences for TTS."""
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r'[.!?]', text) if p.strip()]
    return ".\n\n\n".join(parts) + "."  # Triple line breaks

def playful_wrap(text):
    """Add playful fillers to make responses warmer."""
    fillers = ["Mmm.", "Oooh.", "Hehe.", "Ahh."]
    opener = random.choice(fillers)
    # Add filler at start, pause, then the text
    return f"{opener}\n\n{text}"

def sanitize_text(text):
    """Clean text for TTS."""
    if not text:
        return ""
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def tts_speak(text):
    """Call OpenAI TTS with slower speed."""
    text = sanitize_text(text)
    if not text:
        return None
    try:
        speech = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            speed=TTS_SPEED
        )
        return speech.content
    except Exception as e:
        st.error(f"TTS failed: {e}")
        return None

def extract_relationships(description):
    """Extract relationship words from image description."""
    relationships = []
    patterns = ["brother", "mom", "mother", "dad", "father", "grandmom",
                "grandmother", "granddad", "grandfather", "cousin", "sister", "aunt", "uncle"]
    desc_lower = description.lower()
    for rel in patterns:
        if rel in desc_lower:
            relationships.append(rel)
    return relationships

def check_success(transcript, description):
    """Check if user correctly named someone in the photo."""
    transcript_lower = transcript.lower()
    relationships = extract_relationships(description)

    word_map = {
        "am": "brother",
        "nani": "grandmom",
        "grandmother": "grandmom",
        "mother": "mom",
        "father": "dad",
        "grandfather": "granddad"
    }

    for rel in relationships:
        if rel in transcript_lower:
            return True

    for word, mapped in word_map.items():
        if word in transcript_lower and mapped in relationships:
            return True
        if word in transcript_lower:
            for rel in relationships:
                if mapped in rel or rel in mapped:
                    return True

    return False

def generate_ai_response(transcript, img_description, sys_prompt, attempt, is_success, successes):
    """Generate AI response based on attempt number and success."""

    should_move_on = successes >= MAX_WHO_ELSE or attempt >= MAX_ATTEMPTS

    context = f"""
IMAGE DESCRIPTION: {img_description}

ATTEMPT NUMBER: {attempt}
USER SAID: "{transcript}"
CORRECT ANSWER DETECTED: {"Yes" if is_success else "No"}
TIMES CORRECTLY ANSWERED ON THIS PHOTO: {successes}
SHOULD MOVE TO NEXT PHOTO: {"Yes" if should_move_on else "No"}

Remember:
- Only mention people from the IMAGE DESCRIPTION
- Keep sentences very short (3-6 words)
- Be warm and encouraging
- If SHOULD MOVE TO NEXT PHOTO is Yes, say "Let's see another photo!"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=60,
            temperature=0.7
        )
        ai_text = response.choices[0].message.content.strip()
        if not ai_text:
            return "Mmm, good! Tell me more!"
        return ai_text
    except Exception as e:
        st.error(f"AI error: {e}")
        return "Mmm, good! Tell me more!"

# ---------------- SESSION STATE ----------------
defaults = {
    "idx": 0,
    "attempt": 1,
    "successes": 0,  # Track correct answers per photo
    "sarah_text": "",
    "status": "ready",  # ready, listening, thinking, talking
    "audio_bytes": None,
    "has_spoken": False,
    "should_advance": False,
    "all_done": False
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------- DATA ----------------
with open("data/image_data.json") as f:
    images = json.load(f)
with open("system_prompt.txt") as f:
    sys_prompt = f.read()

total_photos = len(images)

# ---------------- STYLE ----------------
# Dynamic colors based on state
state_colors = {
    "ready": "#9dbdb1",      # Calm green
    "listening": "#f4a261",  # Warm orange
    "thinking": "#e9c46a",   # Yellow (with pulse)
    "talking": "#9dbdb1"     # Calm green
}

current_color = state_colors.get(st.session_state.status, "#9dbdb1")
is_thinking = st.session_state.status == "thinking"

st.markdown(f"""
<style>
header, footer {{visibility: hidden;}}
.block-container {{max-width:800px;margin:auto;}}

.sarah {{
    font-size: 48px;
    font-weight: 900;
    padding: 35px;
    border-radius: 30px;
    border: 6px solid {current_color};
    text-align: center;
    margin-bottom: 10px;
    transition: border-color 0.3s ease;
}}

.status {{
    text-align: center;
    font-size: 24px;
    color: #7a7a7a;
    margin-bottom: 20px;
}}

.progress {{
    text-align: center;
    font-size: 20px;
    color: #888;
    margin-bottom: 15px;
    font-weight: 500;
}}

/* Thinking indicator - pulsing animation */
.thinking-indicator {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 12px;
    padding: 20px;
    margin: 20px 0;
}}

.thinking-dot {{
    width: 20px;
    height: 20px;
    background-color: #e9c46a;
    border-radius: 50%;
    animation: pulse 1.4s ease-in-out infinite;
}}

.thinking-dot:nth-child(2) {{
    animation-delay: 0.2s;
}}

.thinking-dot:nth-child(3) {{
    animation-delay: 0.4s;
}}

@keyframes pulse {{
    0%, 100% {{
        transform: scale(0.8);
        opacity: 0.5;
    }}
    50% {{
        transform: scale(1.2);
        opacity: 1;
    }}
}}

/* Talk button - bigger and with state color */
div[data-testid="stAudioRecorder"] button {{
    width: 100% !important;
    height: 400px !important;
    border-radius: 60px !important;
    background-color: {current_color} !important;
    border: 12px solid white !important;
    transition: background-color 0.3s ease;
}}

div[data-testid="stAudioRecorder"] svg {{
    transform: scale(7);
}}

/* Skip button styling */
.skip-btn {{
    text-align: center;
    margin-top: 20px;
}}

.stButton > button {{
    background-color: #ddd;
    color: #666;
    border: none;
    padding: 10px 30px;
    border-radius: 20px;
    font-size: 16px;
}}

/* All done celebration */
.celebration {{
    font-size: 56px;
    font-weight: 900;
    padding: 50px;
    border-radius: 30px;
    border: 8px solid #9dbdb1;
    text-align: center;
    background: linear-gradient(135deg, #f0fff0 0%, #e8f5e9 100%);
}}
</style>
""", unsafe_allow_html=True)

# Handle photo advancement
if st.session_state.should_advance:
    next_idx = st.session_state.idx + 1
    if next_idx >= total_photos:
        st.session_state.all_done = True
    else:
        st.session_state.idx = next_idx
    st.session_state.attempt = 1
    st.session_state.successes = 0
    st.session_state.has_spoken = False
    st.session_state.should_advance = False

# ---------------- ALL DONE STATE ----------------
if st.session_state.all_done:
    st.markdown("<div class='celebration'>All done! Great job, My!</div>", unsafe_allow_html=True)
    celebration_audio = tts_speak("Yay! All done! Great job My! You did so well!")
    if celebration_audio:
        st.audio(celebration_audio, autoplay=True)

    if st.button("Start Over"):
        for key, val in defaults.items():
            st.session_state[key] = val
        st.rerun()
    st.stop()

# ---------------- DISPLAY PHOTO ----------------
current_img = images[st.session_state.idx]
img_path = os.path.join("assets", current_img["file"])

# Progress indicator
st.markdown(f"<div class='progress'>Photo {st.session_state.idx + 1} of {total_photos}</div>", unsafe_allow_html=True)

if os.path.exists(img_path):
    st.image(img_path)

# ---------------- INITIAL SPEECH ----------------
if not st.session_state.has_spoken:
    opening = "Oooh, I see a photo! Who is this?"
    st.session_state.sarah_text = opening
    st.session_state.status = "talking"
    st.session_state.audio_bytes = tts_speak(slow_opening(opening))
    st.session_state.has_spoken = True

# ---------------- DISPLAY SARAH TEXT ----------------
st.markdown(f"<div class='sarah'>{st.session_state.sarah_text}</div>", unsafe_allow_html=True)

# ---------------- THINKING INDICATOR ----------------
if st.session_state.status == "thinking":
    st.markdown("""
    <div class='thinking-indicator'>
        <div class='thinking-dot'></div>
        <div class='thinking-dot'></div>
        <div class='thinking-dot'></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='status'>Sarah is thinking...</div>", unsafe_allow_html=True)
elif st.session_state.status == "listening":
    st.markdown("<div class='status'>Sarah is listening...</div>", unsafe_allow_html=True)
elif st.session_state.status == "talking":
    st.markdown("<div class='status'>Sarah is talking...</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='status'>Tap to talk</div>", unsafe_allow_html=True)

# ---------------- AUDIO PLAY ----------------
if st.session_state.audio_bytes:
    st.audio(st.session_state.audio_bytes, autoplay=True)
    st.session_state.audio_bytes = None

# ---------------- MICROPHONE ----------------
audio_input = audio_recorder(text="", neutral_color=current_color, icon_size="4x")

# ---------------- SKIP BUTTON ----------------
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("Skip Photo", key="skip"):
        st.session_state.should_advance = True
        st.rerun()

# ---------------- INTERACTION ----------------
# Process audio immediately when received
if audio_input:
    # Transcribe directly from bytes
    try:
        with open("input.wav", "wb") as f:
            f.write(audio_input)

        with open("input.wav", "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            ).text.strip()
    except Exception as e:
        transcript = ""

    # Clean up
    if os.path.exists("input.wav"):
        os.remove("input.wav")

    if not transcript:
        transcript = "mmm"

    is_success = check_success(transcript, current_img["description"])

    if is_success:
        st.session_state.successes += 1

    ai_text = generate_ai_response(
        transcript,
        current_img["description"],
        sys_prompt,
        st.session_state.attempt,
        is_success,
        st.session_state.successes
    )

    st.session_state.sarah_text = ai_text
    st.session_state.audio_bytes = tts_speak(playful_wrap(add_pauses(ai_text)))

    # Handle progression
    should_move = st.session_state.successes >= MAX_WHO_ELSE or st.session_state.attempt >= MAX_ATTEMPTS
    if should_move or "another photo" in ai_text.lower() or "next" in ai_text.lower():
        st.session_state.should_advance = True
    elif not is_success:
        st.session_state.attempt += 1

    st.rerun()
