import streamlit as st
import openai
import json
import os
from audio_recorder_streamlit import audio_recorder

# ---------------- CONFIG ----------------
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=api_key)

# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "sarah_text" not in st.session_state:
    st.session_state.sarah_text = ""
if "status" not in st.session_state:
    st.session_state.status = ""
if "has_spoken" not in st.session_state:
    st.session_state.has_spoken = False
if "audio_bytes" not in st.session_state:
    st.session_state.audio_bytes = None

# ---------------- STYLE ----------------
st.markdown("""
<style>
header, footer {visibility: hidden;}

.block-container {
    max-width: 800px;
    margin: auto;
}

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

/* HUGE TAP BUTTON */
div[data-testid="stAudioRecorder"] button {
    width: 100% !important;
    height: 300px !important;
    border-radius: 60px !important;
    background-color: #9dbdb1 !important;
    border: 10px solid white !important;
}

div[data-testid="stAudioRecorder"] svg {
    transform: scale(6);
}
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

# ---------------- INITIAL SPEECH (ON IMAGE LOAD) ----------------
if not st.session_state.has_spoken:
    opening_text = "I see people together. Who is this?"
    st.session_state.sarah_text = opening_text
    st.session_state.status = "Sarah is talking…"

    ssml = f"""
    <speak>
      <prosody rate="slow" pitch="+2st">
        {opening_text}
      </prosody>
    </speak>
    """

    speech = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=ssml
    )

    st.session_state.audio_bytes = speech.content
    st.session_state.has_spoken = True

# ---------------- DISPLAY TEXT ----------------
st.markdown(f"<div class='sarah'>{st.session_state.sarah_text}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='status'>{st.session_state.status}</div>", unsafe_allow_html=True)

# ---------------- AUDIO PLAYBACK (HIDDEN UI) ----------------
if st.session_state.audio_bytes:
    st.audio(st.session_state.audio_bytes, autoplay=True)
    st.session_state.audio_bytes = None

# ---------------- MIC ----------------
audio_input = audio_recorder(text="", neutral_color="#9dbdb1", icon_size="4x")

# ---------------- INTERACTION ----------------
if audio_input:
    st.session_state.status = "Sarah is listening…"
    with open("input.wav", "wb") as f:
        f.write(audio_input)

    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=open("input.wav", "rb")
    ).text

    st.session_state.status = "Sarah is thinking…"

    image_rules = f"""
WHO MODE:
- Only talk about people in this description:
  "{current_img['description']}"
- Do NOT guess names.
- Do NOT add details.
- Structure:
  1) Say one thing you see
  2) One playful reaction
  3) Ask exactly: "Who is this?"
"""

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "system", "content": image_rules},
            {"role": "user", "content": transcript}
        ],
        max_completion_tokens=50
    )

    ai_text = response.choices[0].message.content
    st.session_state.sarah_text = ai_text
    st.session_state.status = "Sarah is talking…"

    ssml = f"""
    <speak>
      <prosody rate="slow" pitch="+2st">
        {ai_text}
      </prosody>
    </speak>
    """

    speech = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=ssml
    )

    st.session_state.audio_bytes = speech.content
    st.rerun()


