import streamlit as st
import openai
import json
import os
import re
import random
import hashlib
from audio_recorder_streamlit import audio_recorder

# ---------------- CONFIG ----------------
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=api_key)

MAX_ATTEMPTS = 3
MAX_WHO_ELSE = 2
TTS_SPEED = 0.75

# ---------------- HELPERS ----------------
def slow_opening(text):
    """Extra slow word-by-word pacing for opening lines."""
    return "\n\n".join(text.split())

def add_pauses(text):
    """Add longer pauses between sentences for TTS."""
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r'[.!?]', text) if p.strip()]
    return ".\n\n\n".join(parts) + "."

def playful_wrap(text):
    """Add playful fillers to make responses warmer."""
    fillers = ["Mmm.", "Oooh.", "Hehe.", "Ahh."]
    opener = random.choice(fillers)
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
        if word in transcript_lower:
            for rel in relationships:
                if mapped == rel or mapped in rel or rel in mapped:
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
            return "Mmm, tell me more!"
        return ai_text
    except Exception as e:
        st.error(f"AI error: {e}")
        return "Mmm, tell me more!"

def get_audio_hash(audio_bytes):
    """Get hash of audio bytes to detect duplicates."""
    if not audio_bytes:
        return None
    return hashlib.md5(audio_bytes).hexdigest()

# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "attempt" not in st.session_state:
    st.session_state.attempt = 1
if "successes" not in st.session_state:
    st.session_state.successes = 0
if "sarah_text" not in st.session_state:
    st.session_state.sarah_text = ""
if "audio_bytes" not in st.session_state:
    st.session_state.audio_bytes = None
if "has_spoken" not in st.session_state:
    st.session_state.has_spoken = False
if "all_done" not in st.session_state:
    st.session_state.all_done = False
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None
if "recorder_key" not in st.session_state:
    st.session_state.recorder_key = 0

# ---------------- DATA ----------------
with open("data/image_data.json") as f:
    images = json.load(f)
with open("system_prompt.txt") as f:
    sys_prompt = f.read()

total_photos = len(images)

# ---------------- STYLE ----------------
st.markdown("""
<style>
header, footer {visibility: hidden;}
.block-container {max-width:800px;margin:auto;}

.sarah {
    font-size: 48px;
    font-weight: 900;
    padding: 35px;
    border-radius: 30px;
    border: 6px solid #9dbdb1;
    text-align: center;
    margin-bottom: 10px;
}

.status {
    text-align: center;
    font-size: 24px;
    color: #7a7a7a;
    margin-bottom: 20px;
}

.progress {
    text-align: center;
    font-size: 20px;
    color: #888;
    margin-bottom: 15px;
    font-weight: 500;
}

div[data-testid="stAudioRecorder"] button {
    width: 100% !important;
    height: 400px !important;
    border-radius: 60px !important;
    background-color: #9dbdb1 !important;
    border: 12px solid white !important;
}

div[data-testid="stAudioRecorder"] svg {
    transform: scale(7);
}

.stButton > button {
    background-color: #ddd;
    color: #666;
    border: none;
    padding: 10px 30px;
    border-radius: 20px;
    font-size: 16px;
}

.celebration {
    font-size: 56px;
    font-weight: 900;
    padding: 50px;
    border-radius: 30px;
    border: 8px solid #9dbdb1;
    text-align: center;
    background: linear-gradient(135deg, #f0fff0 0%, #e8f5e9 100%);
}
</style>
""", unsafe_allow_html=True)

# ---------------- ALL DONE STATE ----------------
if st.session_state.all_done:
    st.markdown("<div class='celebration'>All done! Great job, My!</div>", unsafe_allow_html=True)
    celebration_audio = tts_speak("Yay! All done! Great job My! You did so well!")
    if celebration_audio:
        st.audio(celebration_audio, autoplay=True)

    if st.button("Start Over"):
        st.session_state.idx = 0
        st.session_state.attempt = 1
        st.session_state.successes = 0
        st.session_state.sarah_text = ""
        st.session_state.audio_bytes = None
        st.session_state.has_spoken = False
        st.session_state.all_done = False
        st.session_state.last_audio_hash = None
        st.session_state.recorder_key += 1
        st.rerun()
    st.stop()

# ---------------- DISPLAY PHOTO ----------------
current_img = images[st.session_state.idx]
img_path = os.path.join("assets", current_img["file"])

st.markdown(f"<div class='progress'>Photo {st.session_state.idx + 1} of {total_photos}</div>", unsafe_allow_html=True)

if os.path.exists(img_path):
    st.image(img_path)

# ---------------- INITIAL SPEECH ----------------
if not st.session_state.has_spoken:
    opening = "Oooh, I see a photo! Who is this?"
    st.session_state.sarah_text = opening
    st.session_state.audio_bytes = tts_speak(slow_opening(opening))
    st.session_state.has_spoken = True

# ---------------- DISPLAY SARAH TEXT ----------------
st.markdown(f"<div class='sarah'>{st.session_state.sarah_text}</div>", unsafe_allow_html=True)
st.markdown("<div class='status'>Tap and hold to talk</div>", unsafe_allow_html=True)

# ---------------- AUDIO PLAY ----------------
if st.session_state.audio_bytes:
    st.audio(st.session_state.audio_bytes, autoplay=True)
    st.session_state.audio_bytes = None

# ---------------- MICROPHONE ----------------
# Use key to reset component, pause_threshold for auto-stop on silence
audio_input = audio_recorder(
    text="",
    icon_size="4x",
    pause_threshold=2.0,  # Stop after 2 seconds of silence
    sample_rate=16000,
    key=f"recorder_{st.session_state.recorder_key}"
)

# ---------------- SKIP BUTTON ----------------
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("Skip Photo"):
        st.session_state.idx = (st.session_state.idx + 1) % total_photos
        if st.session_state.idx == 0:
            st.session_state.all_done = True
        st.session_state.attempt = 1
        st.session_state.successes = 0
        st.session_state.has_spoken = False
        st.session_state.last_audio_hash = None
        st.session_state.recorder_key += 1
        st.rerun()

# ---------------- INTERACTION ----------------
if audio_input:
    # Check if this is new audio (not the same as last processed)
    audio_hash = get_audio_hash(audio_input)

    if audio_hash and audio_hash != st.session_state.last_audio_hash:
        st.session_state.last_audio_hash = audio_hash

        # Transcribe
        transcript = ""
        try:
            with open("input.wav", "wb") as f:
                f.write(audio_input)
            with open("input.wav", "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                ).text.strip()
            os.remove("input.wav")
        except Exception as e:
            st.error(f"Transcription error: {e}")
            transcript = ""

        if not transcript:
            transcript = "mmm"

        # Check success
        is_success = check_success(transcript, current_img["description"])
        if is_success:
            st.session_state.successes += 1

        # Generate response
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
            # Move to next photo
            st.session_state.idx += 1
            if st.session_state.idx >= total_photos:
                st.session_state.all_done = True
            st.session_state.attempt = 1
            st.session_state.successes = 0
            st.session_state.has_spoken = False
            st.session_state.last_audio_hash = None
            st.session_state.recorder_key += 1
        elif not is_success:
            st.session_state.attempt += 1
            st.session_state.recorder_key += 1

        st.rerun()
