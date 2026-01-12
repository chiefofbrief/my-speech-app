import streamlit as st
import openai
import json
import os
from audio_recorder_streamlit import audio_recorder

# ---------------- CONFIG ----------------
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=api_key)

# ---------------- SESSION ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "sarah_text" not in st.session_state:
    st.session_state.sarah_text = ""
if "status" not in st.session_state:
    st.session_state.status = ""
if "greeted" not in st.session_state:
    st.session_state.greeted = False

# ---------------- STYLE ----------------
st.markdown("""
<style>
header, footer {visibility: hidden;}
.sarah {
    font-size: 40px;
    font-weight: 900;
    padding: 25px;
    border-radius: 30px;
    border: 6px solid #9dbdb1;
    text-align: center;
}
.status {
    text-align: center;
    font-size: 24px;
    color: #888;
}
div[data-testid="stAudioRecorder"] > button {
    width: 100%;
    height: 220px;
    border-radius: 50px;
    background-color: #9dbdb1;
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

# ---------------- GREETING ----------------
if not st.session_state.greeted:
    greeting = "Hi My! Let’s look together!"
    speech = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=greeting
    )
    st.session_state.sarah_text = greeting
    st.session_state.audio = speech.content
    st.session_state.greeted = True

# ---------------- UI ----------------
if os.path.exists(img_path):
    st.image(img_path)

st.markdown(f"<div class='sarah'>{st.session_state.sarah_text}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='status'>{st.session_state.status}</div>", unsafe_allow_html=True)

if "audio" in st.session_state:
    st.audio(st.session_state.audio, autoplay=True)
    del st.session_state.audio

audio_bytes = audio_recorder(text="", neutral_color="#9dbdb1", icon_size="4x")

# ---------------- LOGIC ----------------
if audio_bytes:
    st.session_state.status = "Listening…"
    st.rerun()

if st.session_state.status == "Listening…":
    with open("input.wav", "wb") as f:
        f.write(audio_bytes)

    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=open("input.wav", "rb")
    ).text

    st.session_state.status = "Thinking…"

    image_rules = f"""
WHO MODE:
- Only talk about people in this description:
  "{current_img['description']}"
- Do NOT guess names.
- Do NOT add details.
- Structure:
  1) One thing you see
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

    speech = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=ai_text
    )

    st.session_state.sarah_text = ai_text
    st.session_state.audio = speech.content
    st.session_state.status = "Talking…"
    st.rerun()

