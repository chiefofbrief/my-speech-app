import streamlit as st
import openai
import json
import os
import re
import random

# ---------------- CONFIG ----------------
try:
    api_key = st.secrets.get("OPENAI_API_KEY") or st.secrets.get("openai_api_key")
except:
    api_key = None
api_key = api_key or os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=api_key)

MIN_TURNS_PER_PHOTO = 4
MAX_TURNS_PER_PHOTO = 6
TTS_SPEED = 0.75

# All possible relationship options (shown as bubbles)
ALL_RELATIONSHIPS = ["Mom", "Dad", "Brother", "Sister", "Grandmom", "Granddad", "Cousin", "Aunt", "Uncle"]

# ---------------- HELPERS ----------------
def slow_text(text):
    """Add pauses between sentences for TTS."""
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r'[.!?]', text) if p.strip()]
    return ".\n\n\n".join(parts) + "."

def playful_wrap(text):
    """Add playful fillers."""
    fillers = ["Mmm.", "Oooh.", "Hehe.", "Ahh.", "Yay."]
    opener = random.choice(fillers)
    return f"{opener}\n\n{text}"

def sanitize_text(text):
    if not text:
        return ""
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def tts_speak(text):
    """Call OpenAI TTS."""
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
            # Normalize to display form
            if rel in ["mother", "mom"]:
                relationships.append("Mom")
            elif rel in ["father", "dad"]:
                relationships.append("Dad")
            elif rel in ["grandmother", "grandmom"]:
                relationships.append("Grandmom")
            elif rel in ["grandfather", "granddad"]:
                relationships.append("Granddad")
            else:
                relationships.append(rel.capitalize())
    return list(set(relationships))

def generate_response(selection, img_description, turn, is_correct, ready_to_move):
    """Generate Sarah's response based on selection."""

    people_in_photo = extract_relationships(img_description)

    if turn == 1:
        phase = "OPENING"
        instruction = "First turn! Be excited about the photo. Ask who they see."
    elif is_correct and not ready_to_move:
        phase = "CELEBRATING"
        instruction = f"They correctly said {selection}! Celebrate big! Then ask 'Who else do you see?'"
    elif is_correct and ready_to_move:
        phase = "WRAPPING UP"
        instruction = f"They said {selection}! Big celebration, then say 'Let's see another photo!'"
    elif ready_to_move:
        phase = "WRAPPING UP"
        instruction = "Time to move on. Celebrate their participation, say 'Let's see another photo!'"
    else:
        phase = "ENCOURAGING"
        instruction = f"They picked {selection}. Be warm and encouraging! Give a gentle hint about someone who IS in the photo: {people_in_photo}"

    prompt = f"""You are Sarah, a warm playful friend talking to My (a young woman).

IMAGE: {img_description}
TURN: {turn}
PHASE: {phase}
MY PICKED: {selection}
CORRECT: {is_correct}

{instruction}

RULES:
- Very short sentences (3-6 words max)
- Be warm, playful, encouraging
- NEVER say she's wrong
- Only say "Let's see another photo!" if PHASE is WRAPPING UP
- Add sounds like "Oooh" or "Mmm" or "Hehe"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except:
        if is_correct:
            return f"Yay! You see {selection}! Who else?"
        return "Mmm, good try! Who else do you see?"

# ---------------- SESSION STATE ----------------
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "turn" not in st.session_state:
    st.session_state.turn = 0
if "sarah_text" not in st.session_state:
    st.session_state.sarah_text = ""
if "audio_bytes" not in st.session_state:
    st.session_state.audio_bytes = None
if "has_spoken" not in st.session_state:
    st.session_state.has_spoken = False
if "all_done" not in st.session_state:
    st.session_state.all_done = False
if "found_people" not in st.session_state:
    st.session_state.found_people = []

# ---------------- DATA ----------------
with open("data/image_data.json") as f:
    images = json.load(f)

total_photos = len(images)

# ---------------- STYLE ----------------
st.markdown("""
<style>
header, footer {visibility: hidden;}
.block-container {max-width: 900px; margin: auto; padding-top: 1rem;}

.sarah {
    font-size: 42px;
    font-weight: 900;
    padding: 30px;
    border-radius: 30px;
    border: 6px solid #9dbdb1;
    text-align: center;
    margin-bottom: 20px;
    background: white;
}

.progress {
    text-align: center;
    font-size: 20px;
    color: #888;
    margin-bottom: 15px;
}

/* Bubble container */
.bubble-container {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 15px;
    padding: 20px;
    margin-top: 20px;
}

/* Individual bubbles */
.stButton > button {
    border-radius: 50px !important;
    padding: 25px 40px !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    border: 4px solid white !important;
    box-shadow: 0 8px 20px rgba(0,0,0,0.15) !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
    min-width: 140px !important;
}

.stButton > button:hover {
    transform: scale(1.1) !important;
    box-shadow: 0 12px 30px rgba(0,0,0,0.2) !important;
}

/* Bubble colors */
.stButton:nth-child(1) > button { background: linear-gradient(135deg, #FFB6C1, #FF69B4) !important; color: white !important; }
.stButton:nth-child(2) > button { background: linear-gradient(135deg, #87CEEB, #4169E1) !important; color: white !important; }
.stButton:nth-child(3) > button { background: linear-gradient(135deg, #98FB98, #32CD32) !important; color: white !important; }
.stButton:nth-child(4) > button { background: linear-gradient(135deg, #DDA0DD, #9370DB) !important; color: white !important; }
.stButton:nth-child(5) > button { background: linear-gradient(135deg, #FFD700, #FFA500) !important; color: white !important; }
.stButton:nth-child(6) > button { background: linear-gradient(135deg, #20B2AA, #008B8B) !important; color: white !important; }
.stButton:nth-child(7) > button { background: linear-gradient(135deg, #F0E68C, #DAA520) !important; color: white !important; }
.stButton:nth-child(8) > button { background: linear-gradient(135deg, #E6E6FA, #9370DB) !important; color: white !important; }
.stButton:nth-child(9) > button { background: linear-gradient(135deg, #FFA07A, #FF6347) !important; color: white !important; }

/* Next photo button */
.next-btn > button {
    background: #ddd !important;
    color: #666 !important;
    font-size: 18px !important;
    padding: 12px 30px !important;
}

.celebration {
    font-size: 48px;
    font-weight: 900;
    padding: 50px;
    border-radius: 30px;
    border: 8px solid #9dbdb1;
    text-align: center;
    background: linear-gradient(135deg, #f0fff0 0%, #e8f5e9 100%);
}

/* Found indicator */
.found {
    text-align: center;
    font-size: 18px;
    color: #4CAF50;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- ALL DONE ----------------
if st.session_state.all_done:
    st.markdown("<div class='celebration'>All done! Great job, My!</div>", unsafe_allow_html=True)
    celebration_audio = tts_speak("Yay! All done! Great job My! You did so well! I'm so proud of you!")
    if celebration_audio:
        st.audio(celebration_audio, autoplay=True)

    if st.button("Start Over"):
        st.session_state.idx = 0
        st.session_state.turn = 0
        st.session_state.sarah_text = ""
        st.session_state.audio_bytes = None
        st.session_state.has_spoken = False
        st.session_state.all_done = False
        st.session_state.found_people = []
        st.rerun()
    st.stop()

# ---------------- CURRENT PHOTO ----------------
current_img = images[st.session_state.idx]
img_path = os.path.join("assets", current_img["file"])
people_in_photo = extract_relationships(current_img["description"])

# Progress
st.markdown(f"<div class='progress'>Photo {st.session_state.idx + 1} of {total_photos}</div>", unsafe_allow_html=True)

# Photo
if os.path.exists(img_path):
    st.image(img_path)

# ---------------- INITIAL SPEECH ----------------
if not st.session_state.has_spoken:
    opening = "Oooh, look at this photo! Who do you see?"
    st.session_state.sarah_text = opening
    st.session_state.audio_bytes = tts_speak(slow_text(opening))
    st.session_state.has_spoken = True
    st.session_state.turn = 1
    st.session_state.found_people = []

# Sarah's text
st.markdown(f"<div class='sarah'>{st.session_state.sarah_text}</div>", unsafe_allow_html=True)

# Show who they've found
if st.session_state.found_people:
    found_str = ", ".join(st.session_state.found_people)
    st.markdown(f"<div class='found'>Found: {found_str}</div>", unsafe_allow_html=True)

# Audio playback
if st.session_state.audio_bytes:
    st.audio(st.session_state.audio_bytes, autoplay=True)
    st.session_state.audio_bytes = None

# ---------------- BUBBLE OPTIONS ----------------
st.write("")  # Spacing

# Create bubble grid
cols = st.columns(3)
for i, relationship in enumerate(ALL_RELATIONSHIPS):
    col_idx = i % 3
    with cols[col_idx]:
        # Dim the button if already found
        label = f"✓ {relationship}" if relationship in st.session_state.found_people else relationship
        if st.button(label, key=f"bubble_{relationship}", disabled=(relationship in st.session_state.found_people)):
            # Handle selection
            st.session_state.turn += 1

            is_correct = relationship in people_in_photo
            if is_correct and relationship not in st.session_state.found_people:
                st.session_state.found_people.append(relationship)

            ready_to_move = st.session_state.turn >= MIN_TURNS_PER_PHOTO

            # Generate response
            ai_text = generate_response(
                relationship,
                current_img["description"],
                st.session_state.turn,
                is_correct,
                ready_to_move
            )

            st.session_state.sarah_text = ai_text
            st.session_state.audio_bytes = tts_speak(playful_wrap(slow_text(ai_text)))

            # Check if should advance
            should_advance = (
                (ready_to_move and "another photo" in ai_text.lower()) or
                st.session_state.turn >= MAX_TURNS_PER_PHOTO or
                (len(st.session_state.found_people) >= len(people_in_photo) and st.session_state.turn >= 3)
            )

            if should_advance:
                st.session_state.idx += 1
                if st.session_state.idx >= total_photos:
                    st.session_state.all_done = True
                st.session_state.turn = 0
                st.session_state.has_spoken = False
                st.session_state.found_people = []

            st.rerun()

# ---------------- NEXT PHOTO BUTTON ----------------
st.write("")
st.write("")
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    st.markdown('<div class="next-btn">', unsafe_allow_html=True)
    if st.button("Next Photo →"):
        st.session_state.idx += 1
        if st.session_state.idx >= total_photos:
            st.session_state.all_done = True
        st.session_state.turn = 0
        st.session_state.has_spoken = False
        st.session_state.found_people = []
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
