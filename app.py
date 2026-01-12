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

# ---------------- HELPERS ----------------
def slow_text(text):
    """Add extra pauses for slower TTS."""
    parts = [p.strip() for p in re.split(r'[.!?]', text) if p.strip()]
    return ".\n\n\n".join(parts)  # triple line breaks for extra pause

def gentle_repeat(text):
    """Repeat key noun phrases gently."""
    if not text:
        return ""
    for line in text.strip().split("\n"):
        if "your " in line.lower():
            return text + "\n\n" + line.strip()
    return text

def playful_expand(text):
    """Make short AI outputs more playful and encouraging."""
    fillers = ["Mmm", "Oooh", "Hehe", "Ahh"]
    if len(text.split()) <= 8:
        text = f"{random.choice(fillers)}. {text}. {random.choice(fillers)}."
        text += f"\n\n{random.choice(fillers)}, that’s wonderful!"
    return text

def sanitize_text(text):
    """Clean text for TTS."""
    if not text:
        return ""
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()

def tts_speak(text):
    """Call OpenAI TTS safely."""
    text = sanitize_text(text)
    if not text:
        return None
    try:
        speech = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text
        )
        return speech.content
    except Exception as e:
        st.error(f"TTS failed: {e}")
        return None

def generate_ai_response(transcript, img_description, sys_prompt):
    """Generate AI response with rules and fallback."""
    image_rules = f"""
WHO MODE:
- Only talk about people in this description:
  "{img_description}"
- Do NOT guess names
- Do NOT add details
- Structure:
  1) One thing you see
  2) One playful reaction
  3) Ask exactly: "Who is this?"
- Gentle repetition is allowed
"""
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "system", "content": image_rules},
                {"role": "user", "content": transcript}
            ],
            max_completion_tokens=70  # slightly longer for playful follow-ups
        )
        ai_text = response.choices[0].message.content.strip()
        if not ai_text:
            return "Mmm, good! Tell me more!"
        return ai_text
    except Exception:
        return "Mmm, good! Tell me more!"

# Map simple sounds to relationships
sound_map = {
    "am": "your brother",
    "nani": "your grandmom"
}

# ---------------- SESSION STATE ----------------
for key in ["idx","sarah_text","status","has_spoken","audio_bytes"]:
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.idx is None:
    st.session_state.idx = 0
if st.session_state.has_spoken is None:
    st.session_state.has_spoken = False

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

current_img = images[st.session_state.idx % len(images)]
img_path = os.path.join("assets", current_img["file"])
if os.path.exists(img_path):
    st.image(img_path)

# ---------------- INITIAL SPEECH ----------------
if not st.session_state.has_spoken:
    opening_text = "I see people together. Who is this?"
    st.session_state.sarah_text = opening_text
    st.session_state.status = "Sarah is talking…"
    st.session_state.audio_bytes = tts_speak(playful_expand(slow_text(opening_text)))
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
    st.session_state.status = "Sarah is listening…"
    with open("input.wav","wb") as f:
        f.write(audio_input)

    # Transcribe
    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=open("input.wav","rb")
        ).text.strip()
    except Exception:
        transcript = ""

    if not transcript:
        transcript = "mmm"

    transcript_mapped = sound_map.get(transcript.lower(), transcript)

    ai_text = generate_ai_response(transcript_mapped, current_img["description"], sys_prompt)

    # Slow, repeat, playful, encouraging
    final_spoken = gentle_repeat(slow_text(ai_text))
    final_spoken = playful_expand(final_spoken)

    st.session_state.sarah_text = ai_text
    st.session_state.audio_bytes = tts_speak(final_spoken)
    st.session_state.status = "Sarah is talking…"

# Play audio if available
if st.session_state.audio_bytes:
    st.audio(st.session_state.audio_bytes, autoplay=True)
    st.session_state.audio_bytes = None










