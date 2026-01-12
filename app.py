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
except Exception:
    st.error("Missing API Key. Please add it to Streamlit Secrets.")
    st.stop()

# --- 2. SESSION STATE ---
if 'idx' not in st.session_state:
    st.session_state.idx = 0
if 'ai_text' not in st.session_state:
    st.session_state.ai_text = ""
if 'greeted' not in st.session_state:
    st.session_state.greeted = False

# --- 3. MASSIVE UI STYLING (iPad Optimized) ---
st.markdown("""
    <style>
        header, footer {visibility: hidden;}
        .main .block-container {padding: 1rem; max-width: 600px;}
        
        /* The Image */
        img {
            border-radius: 25px; 
            max-height: 320px !important;
            width: auto;
            display: block;
            margin: 0 auto 10px auto;
        }

        /* Sarah's Large Text Bubble */
        .sarah-bubble {
            font-size: 34px !important;
            font-weight: 800;
            color: #2c3e50;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 20px;
            border: 4px solid #9dbdb1;
            text-align: center;
            margin-bottom: 15px;
        }

        /* THE MASSIVE TAP TO TALK BUTTON */
        div[data-testid="stAudioRecorder"] > button {
            width: 100% !important;
            height: 180px !important;
            border-radius: 40px !important;
            background-color: #9dbdb1 !important;
            border: 5px solid white !important;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1) !important;
        }
        div[data-testid="stAudioRecorder"] svg { transform: scale(3); }
    </style>
""", unsafe_allow_html=True)

# --- 4. PREPARE DATA ---
with open("data/image_data.json", "r") as f: images = json.load(f)
with open("system_prompt.txt", "r") as f: sys_prompt = f.read()

current_img = images[st.session_state.idx % len(images)]
img_path = os.path.join("assets", current_img["file"])

# --- 5. INITIAL GREETING (Sarah's First Words) ---
if not st.session_state.greeted:
    welcome = "Hey My! Let's look at some old photos!"
    speech = client.audio.speech.create(model="tts-1", voice="nova", input=welcome)
    st.session_state.ai_text = welcome
    st.session_state.active_audio = speech.content
    st.session_state.greeted = True

# --- 6. UI LAYOUT ---
if os.path.exists(img_path):
    st.image(img_path)

st.markdown(f'<div class="sarah-bubble">{st.session_state.ai_text}</div>', unsafe_allow_html=True)

# Autoplay Audio
if 'active_audio' in st.session_state and st.session_state.active_audio:
    st.audio(st.session_state.active_audio, format="audio/mp3", autoplay=True)
    st.session_state.active_audio = None

# Huge Controls
c1, c2 = st.columns([4, 1])
with c1:
    audio_bytes = audio_recorder(text="", neutral_color="#9dbdb1", icon_size="4x")
with c2:
    st.write("") # Spacer
    if st.button("Next ➔", use_container_width=True):
        st.session_state.idx += 1
        st.session_state.greeted = False # Trigger new greeting
        st.rerun()

# --- 7. FAST RESPONSE LOGIC ---
if audio_bytes:
    with open("tmp.wav", "wb") as f: f.write(audio_bytes)
    
    # 1. Faster STT
    transcript = client.audio.transcriptions.create(model="whisper-1", file=open("tmp.wav", "rb")).text
    
    # Check for 'Next' command
    if "next" in transcript.lower():
        st.session_state.idx += 1
        st.session_state.greeted = False
        st.rerun()

    # 2. Faster Brain (GPT-5 Mini)
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "system", "content": f"IMAGE: {current_img['description']}"},
            {"role": "user", "content": transcript}
        ],
        max_tokens=40 # Cut latency by forcing short responses
    )
    ai_text = response.choices[0].message.content
    
    # 3. Faster TTS (Nova)
    speech = client.audio.speech.create(model="tts-1", voice="nova", input=ai_text)
    
    st.session_state.ai_text = ai_text
    st.session_state.active_audio = speech.content
    st.rerun()
