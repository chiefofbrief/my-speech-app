import streamlit as st
import openai
import json
import os
from audio_recorder_streamlit import audio_recorder

# --- 1. CONFIGURATION ---
try:
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    client = openai.Client(api_key=openai.api_key)
except Exception as e:
    st.error(f"Failed to initialize OpenAI client. Make sure your OPENAI_API_KEY is set. Error: {e}")
    st.stop()

try:
    with open("system_prompt.txt", "r") as f:
        sys_prompt = f.read()
except FileNotFoundError:
    st.error("The 'system_prompt.txt' file was not found. Please create it.")
    st.stop()

try:
    with open("data/image_data.json", "r") as f:
        image_data = json.load(f)
except FileNotFoundError:
    st.error("The 'data/image_data.json' file was not found. Please create it.")
    st.stop()
except json.JSONDecodeError:
    st.error("The 'data/image_data.json' file is not a valid JSON. Please check its content.")
    st.stop()


# --- 2. SESSION STATE INITIALIZATION ---
if 'turn_count' not in st.session_state:
    st.session_state.turn_count = 0
if 'image_index' not in st.session_state:
    st.session_state.image_index = 0
if 'history' not in st.session_state:
    st.session_state.history = []
if 'ai_speech' not in st.session_state:
    st.session_state.ai_speech = "Tap the button below to start!"


# --- 3. UI STYLING ---
st.markdown("""
    <style>
        /* Hide Streamlit's default header and footer */
        header, footer {visibility: hidden;}
        
        /* Center align all content */
        .main .block-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding-top: 2rem;
        }
        
        /* Style for the AI's spoken text container */
        .ai-text-container {
            font-size: 32px !important; 
            font-weight: bold;
            color: #333;
            padding: 20px;
            border-radius: 15px;
            background-color: #f0f2f6;
            min-height: 120px;
            width: 90%;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Massive 'Tap to Talk' button styling */
        div[data-testid="stAudioRecorder"] > button {
            background-color: #9dbdb1;
            color: white;
            height: 120px;
            width: 100%; 
            border-radius: 60px;
            font-size: 24px;
            font-weight: bold;
            border: none;
            margin-top: 10px;
        }
    </style>
""", unsafe_allow_html=True)


# --- 4. LAYOUT AND LOGIC ---

# Ensure image_index is within bounds
if len(image_data) > 0:
    st.session_state.image_index %= len(image_data)
    current_image_info = image_data[st.session_state.image_index]
    
    # FIXED: Changed ["filename"] to ["file"] to match your JSON
    current_image_path = os.path.join("assets", current_image_info.get("file", ""))
    current_image_description = current_image_info.get("description", "")
else:
    st.error("No images found in image_data.json")
    st.stop()

# Top: Display the current image
if os.path.exists(current_image_path):
    st.image(current_image_path, width=500)
else:
    st.warning(f"Image not found at path: {current_image_path}")

# Middle: Display the AI's spoken text
st.markdown(f'<div class="ai-text-container">{st.session_state.ai_speech}</div>', unsafe_allow_html=True)

# Bottom: Audio recorder and Next button
col1, col2 = st.columns([3, 1])

with col1:
    audio_bytes = audio_recorder(
        text="Tap to Talk",
        recording_color="#e8b62c",
        neutral_color="#9dbdb1",
        icon_name="microphone",
        pause_threshold=2.0,
    )

with col2:
    st.write("") # Spacer
    st.write("") # Spacer
    if st.button("Next Picture"):
        st.session_state.image_index += 1
        st.session_state.turn_count = 0
        st.session_state.history = []
        st.session_state.ai_speech = "Tap to start!"
        st.rerun()


# --- 5. LOGIC FLOW ---
if audio_bytes:
    # Save recorded audio
    with open("input.wav", "wb") as f:
        f.write(audio_bytes)

    # STT: Transcribe audio
    try:
        with open("input.wav", "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcript = transcript_response.text
        
        # Log user input
        st.session_state.history.append({"role": "user", "content": transcript})
    except Exception as e:
        st.error(f"Error in transcription: {e}")
        st.stop()

    # Check for verbal "Next" command BEFORE generating AI response
    if "next" in transcript.lower() or "done" in transcript.lower():
        st.session_state.image_index += 1
        st.session_state.turn_count = 0
        st.session_state.history = []
        st.session_state.ai_speech = "Okay, let's look at the next one!"
        st.rerun()

    # Brain (GPT-5 Mini): Get AI response
    try:
        system_context_message = {
            "role": "system",
            "content": f"Current Image Context: {current_image_description}. Turn {st.session_state.turn_count + 1} of 3."
        }
        
        messages_for_api = [
            {"role": "system", "content": sys_prompt},
            system_context_message
        ] + st.session_state.history[-6:] # Keep context window manageable

        completion = client.chat.completions.create(
            model="gpt-5-mini",  # Using the model you requested
            messages=messages_for_api
        )
        ai_response_text = completion.choices[0].message.content
        
        # Update State
        st.session_state.history.append({"role": "assistant", "content": ai_response_text})
        st.session_state.ai_speech = ai_response_text
        st.session_state.turn_count += 1

    except Exception as e:
        st.error(f"Error in chat completion: {e}")
        st.stop()

    # TTS: Convert response to audio
    try:
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice="shimmer",
            speed=0.85,
            input=ai_response_text
        )
        # Save and autoplay
        audio_filename = "response.mp3"
        speech_response.stream_to_file(audio_filename)
        st.audio(audio_filename, autoplay=True)

    except Exception as e:
        st.error(f"Error in text-to-speech: {e}")
        st.stop()

    # Rerun to update UI text immediately
    st.rerun()
    