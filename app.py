import streamlit as st
import openai
import json
import os
import re
from audio_recorder_streamlit import audio_recorder

# ---------------- CONFIG ----------------
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=api_key)

# ---------------- HELPERS ----------------
def slow_text(text):
    """Adds pauses so TTS speaks slower and warmer."""
    parts = text.split(". ")
    return ".\n\n".join(parts)

def gentle_repeat(text):
    """Repeats key noun phrases gently."""
    if not text:
        return ""
    lines = text.strip().split("\n")
    for line in lines:
        if "your " in line.lower():
            return text + "\n\n" + line.strip()
    return text

def sanitize_text(text):
    """Removes problematic characters for TTS."""
    if not text:
        return ""
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()

def tts_speak(text):
    """Calls OpenAI TTS safely, returns bytes or None."""
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
    except openai.error.BadRequestError:
        st.error("TTS request failed. Check text length or content.")
        st.write(text)
        return None
    except Exception as e:
        st.error(f"Unexpected error in TTS: {e}")
        return None

def generate_ai_response(transcript, img_description, sys_prompt):
    """Calls GPT-5-mini with rules and transcript."""
    image_rules = f"""
WHO MODE:
- Only talk about people in this description:
  "{img_description}"
- Do NOT guess names.
- Do NOT add details.
- Structure:
  1) One thing you see
  2) One playful reaction
  3) Ask exactly: "Who is this?"
- Gentle repetition is allowed.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "system", "content": image_rules},
                {"role": "user", "content": transcript}
            ],
            max_completion_tokens=50
        )
        ai_text = response.choices[0].message.content.strip()
        if not ai_text:
            return None
        return ai_text
    except Exception as e:
        st.error(f"Error generating AI response: {e}")
        return None

def encourage_retry():
    """Fallback encouragement text if AI fails."""
    return "Hmm, I didn't catch that. Can you describe what you see a little differently?"

# ---------------- SESSION STATE ----------------
for key in ["idx", "sarah_text", "status", "has_spoken", "audio_bytes"]:
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

.block-container {max-width: 800px; margin: auto;}

.sarah {
    font-size: 40px;
    font-weight: 900;
    padding: 30px;
    border-radius: 30px;
    border: 6px solid #9dbdb1;
    text-align: center;
    margin-bottom: 10px;
}

.status {
    text-align: center;
    font-size: 22px;
    color: #7a7a7a;
    margin-bottom: 20px;
}

/* HUGE MIC BUTTON */
div[data-testid="stAudioRecorder"] button {
    width: 100% !important;
    height: 300px !important;
    border-radius: 60px !important;
    background-color: #9dbdb1 !important;
    border: 10px solid white !important;
}

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

# ---------------- IMAGE ----------------
if os.path.exists(img_path):
    st.image(img_path)

# ---------------- INITIAL SPEECH ----------------
if not st.session_state.has_spoken:
    opening_text = "I see people together. Who is this?"
    spoken_text = slow_text(opening_text)
    st.session_state.sarah_text = opening_text
    st.session_state.status = "Sarah is talking…"
    st.session_state.audio_bytes = tts_speak(spoken_text)
    st.session_state.has_spoken = True

# ---------------- DISPLAY ----------------
st.markdown(f"<div class='sarah'>{st.session_state.sarah_text}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='status'>{st.session_state.status}</div>", unsafe_allow_html=True)

# ---------------- AUDIO PLAY ----------------
if st.session_state.audio_bytes:
    st.audio(st.session_state.audio_bytes, autoplay=True)
    st.session_state.audio_bytes = None

# ---------------- MICROPHONE INPUT ----------------
audio_input = audio_recorder(text="", neutral_color="#9dbdb1", icon_size="4x")

# ---------------- INTERACTION ----------------
if audio_input:
    st.session_state.status = "Sarah is listening…"

    with open("input.wav", "wb") as f:
        f.write(audio_input)

    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=open("input.wav", "rb")
        ).text.strip()
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        transcript = ""

    if not transcript:
        transcript = "No discernible speech detected."

    st.session_state.status = "Sarah is thinking…"

    ai_text = generate_ai_response(transcript, current_img["description"], sys_prompt)
    if not ai_text:
        ai_text = encourage_retry()

    # Apply pacing + repetition
    paced = slow_text(ai_text)
    final_spoken = gentle_repeat(paced)
    if not final_spoken.strip():
        final_spoken = ai_text.strip()

    st.session_state.sarah_text = ai_text
    st.session_state.status = "Sarah is talking…"
    st.session_state.audio_bytes = tts_speak(final_spoken)

    if st.session_state.audio_bytes:
        st.experimental_rerun()
    else:
        st.session_state.status = "Sarah couldn't speak. Try again!"






