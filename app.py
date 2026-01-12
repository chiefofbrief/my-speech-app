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
TTS_SPEED = 0.85  # Slower, more natural pace

# ---------------- HELPERS ----------------
def add_pauses(text):
    """Add natural pauses between sentences for TTS."""
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r'[.!?]', text) if p.strip()]
    return ".\n\n".join(parts) + "."

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

    # Map spoken words to relationship words
    word_map = {
        "am": "brother",
        "nani": "grandmom",
        "grandmother": "grandmom",
        "mother": "mom",
        "father": "dad",
        "grandfather": "granddad"
    }

    # Check direct matches
    for rel in relationships:
        if rel in transcript_lower:
            return True

    # Check mapped words
    for word, mapped in word_map.items():
        if word in transcript_lower and mapped in relationships:
            return True
        # Also check if the mapped word's base is in relationships
        if word in transcript_lower:
            for rel in relationships:
                if mapped in rel or rel in mapped:
                    return True

    return False

def generate_ai_response(transcript, img_description, sys_prompt, attempt, is_success):
    """Generate AI response based on attempt number and success."""

    context = f"""
IMAGE DESCRIPTION: {img_description}

ATTEMPT NUMBER: {attempt}
USER SAID: "{transcript}"
CORRECT ANSWER DETECTED: {"Yes" if is_success else "No"}

Remember:
- Only mention people from the IMAGE DESCRIPTION
- Keep sentences very short (3-6 words)
- Be warm and encouraging
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
    "sarah_text": "",
    "status": "",
    "audio_bytes": None,
    "has_spoken": False,
    "should_advance": False
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------- STYLE ----------------
st.markdown("""
<style>
header, footer {visibility: hidden;}
.block-container {max-width:800px;margin:auto;}
.sarah {font-size:40px;font-weight:900;padding:30px;border-radius:30px;border:6px solid #9dbdb1;text-align:center;margin-bottom:10px;}
.status {text-align:center;font-size:22px;color:#7a7a7a;margin-bottom:20px;}
div[data-testid="stAudioRecorder"] button {width:100% !important;height:300px !important;border-radius:60px !important;background-color:#9dbdb1 !important;border:10px solid white !important;}
div[data-testid="stAudioRecorder"] svg {transform: scale(6);}
</style>
""", unsafe_allow_html=True)

# ---------------- DATA ----------------
with open("data/image_data.json") as f:
    images = json.load(f)
with open("system_prompt.txt") as f:
    sys_prompt = f.read()

# Handle photo advancement
if st.session_state.should_advance:
    st.session_state.idx = (st.session_state.idx + 1) % len(images)
    st.session_state.attempt = 1
    st.session_state.has_spoken = False
    st.session_state.should_advance = False

current_img = images[st.session_state.idx]
img_path = os.path.join("assets", current_img["file"])
if os.path.exists(img_path):
    st.image(img_path)

# ---------------- INITIAL SPEECH ----------------
if not st.session_state.has_spoken:
    opening = "Oooh, I see a photo! Who is this?"
    st.session_state.sarah_text = opening
    st.session_state.status = "Sarah is talking..."
    st.session_state.audio_bytes = tts_speak(add_pauses(opening))
    st.session_state.has_spoken = True

# ---------------- DISPLAY ----------------
st.markdown(f"<div class='sarah'>{st.session_state.sarah_text}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='status'>{st.session_state.status}</div>", unsafe_allow_html=True)

# ---------------- AUDIO PLAY ----------------
if st.session_state.audio_bytes:
    st.audio(st.session_state.audio_bytes, autoplay=True)
    st.session_state.audio_bytes = None

# ---------------- MICROPHONE ----------------
audio_input = audio_recorder(text="", neutral_color="#9dbdb1", icon_size="4x")

# ---------------- INTERACTION ----------------
if audio_input:
    st.session_state.status = "Sarah is listening..."

    # Save and transcribe
    with open("input.wav", "wb") as f:
        f.write(audio_input)

    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=open("input.wav", "rb")
        ).text.strip()
    except Exception:
        transcript = ""

    # Fallback for empty/short sounds
    if not transcript:
        transcript = "mmm"

    # Check for success
    is_success = check_success(transcript, current_img["description"])

    # Generate response
    ai_text = generate_ai_response(
        transcript,
        current_img["description"],
        sys_prompt,
        st.session_state.attempt,
        is_success
    )

    # Update state
    st.session_state.sarah_text = ai_text
    st.session_state.audio_bytes = tts_speak(add_pauses(ai_text))
    st.session_state.status = "Sarah is talking..."

    # Handle progression
    if is_success or st.session_state.attempt >= MAX_ATTEMPTS:
        # Check if AI response suggests moving on
        if "another photo" in ai_text.lower() or "next" in ai_text.lower():
            st.session_state.should_advance = True
        elif is_success:
            st.session_state.attempt = 1  # Reset for "who else" questions
        else:
            st.session_state.should_advance = True
    else:
        st.session_state.attempt += 1

    st.rerun()
