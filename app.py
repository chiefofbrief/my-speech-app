import streamlit as st
import openai
import json
import os
from audio_recorder_streamlit import audio_recorder

# --- 1. CONFIGURATION ---
try:
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
    client = openai.Client(api_key=api_key)
except Exception as e:
    st.error("Missing API Key. Check your Secrets or .env file.")
    st.stop()

# Load Files
def load_file(path):
    with open(path, "r") as f:
        return f.read()

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

# --- 2. SESSION STATE ---
if 'turn_count' not in st.session_state:
    st.session_state.turn_count = 0
if 'image_index' not in st.session_state:
    st.session_state.image_index = 0
if 'ai_speech' not in st.session_state:
    st.session_state.ai_speech = ""
if 'history' not in st.session_state:
    st.session_state.history = []
if 'greeting_played' not in st.session_state:
    st.session_state.greeting_played = False

# --- 3. UI STYLING (Better Layout & Size) ---
st.markdown("""
    <style>
        header, footer {visibility: hidden;}
        .block-container {
            display: flex; flex-direction: column; align-items: center;
            justify-content: center; text-align: center; padding-top: 1rem !important;
        }
        .stImage > img {
            border-radius: 20px; max-height: 400px !important;
            object-fit: contain; box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            margin-bottom: 10px;
        }
        .ai-bubble {
            font-size: 32px !important; font-weight: bold; color: #333;
            background-color: #f7f9fb; padding: 20px; border-radius: 15px;
            width: 90%; min-height: 100px; margin: 15px 0;
            display: flex; align-items: center; justify-content: center;
            border: 2px solid #e1e8ed;
        }
        /* Tap to Talk Button */
        div[data-testid="stAudioRecorder"] > button {
            background-color: #9dbdb1 !important; color: white !important;
            height: 100px !important; width: 100% !important; 
            border-radius: 50px !important; font-size: 24px !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- 4. PREPARE DATA ---
images = load_json("data/image_data.json")
sys_prompt = load_file("system_prompt.txt")
current_idx = st.session_state.image_index % len(images)
img_info = images[current_idx]
img_path = os.path.join("assets", img_info["file"])

# --- 5. THE AUTO-GREETING LOGIC ---
# This runs only once per image to say the 'initial_prompt'
if not st.session_state.greeting_played:
    greeting_text = img_info.get("initial_prompt", "Hi My! Look at this!")
    speech = client.audio.speech.create(
        model="tts-1", voice="nova", speed=1.0, input=greeting_text
    )
    st.session_state.ai_speech = greeting_text
    st.session_state.greeting_played = True
    # We save the content to play below
    st.session_state.active_audio = speech.content

# --- 6. UI LAYOUT ---
if os.path.exists(img_path):
    st.image(img_path)

st.markdown(f'<div class="ai-bubble">{st.session_state.ai_speech}</div>', unsafe_allow_html=True)

# Autoplay Audio (Greeting or Response)
if 'active_audio' in st.session_state and st.session_state.active_audio:
    st.audio(st.session_state.active_audio, format="audio/mp3", autoplay=True)
    st.session_state.active_audio = None # Clear so it doesn't loop

# Controls
col1, col2 = st.columns([4, 1])
with col1:
    audio_bytes = audio_recorder(text="Tap to Talk", neutral_color="#9dbdb1", icon_size="3x")

with col2:
    if st.button("Next ➔"):
        st.session_state.image_index += 1
        st.session_state.turn_count = 0
        st.session_state.greeting_played = False
        st.session_state.history = []
        st.rerun()

# --- 7. CORE CONVERSATION LOGIC ---
if audio_bytes:
    # Save & Transcribe
    with open("temp_in.wav", "wb") as f: f.write(audio_bytes)
    transcript = client.audio.transcriptions.create(
        model="whisper-1", file=open("temp_in.wav", "rb")
    ).text

    # Brain (GPT-5 Mini)
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "system", "content": f"Visual Context: {img_info['description']}"},
            {"role": "user", "content": transcript}
        ]
    )
    ai_text = response.choices[0].message.content

    # TTS
    speech = client.audio.speech.create(model="tts-1", voice="nova", input=ai_text)
    
    # Update State
    st.session_state.ai_speech = ai_text
    st.session_state.active_audio = speech.content
    st.session_state.turn_count += 1
    
    if "next" in transcript.lower():
        st.session_state.image_index += 1
        st.session_state.turn_count = 0
        st.session_state.greeting_played = False
    
    st.rerun()
