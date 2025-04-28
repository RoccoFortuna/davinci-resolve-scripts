"""
This script generates a sound effect based on user input using the ElevenLabs API and adds it to the timeline.
"""

""" --- boilerplate code --- """
#!/usr/bin/env python
resolve = app.GetResolve()  # type: ignore - `app` is a davinci native variable
fusion = resolve.Fusion()
""" --- end of boilerplate code --- """

import os
import datetime
import requests

from utils import get_project_media_folder, move_file_to_media_pool, import_and_append_to_timeline


# Constants
ELEVENLABS_API_KEY = "sk_9d868efc2daeb7615b6b2c60711dc0a99305d7c58216f6da"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/sound-generation"
DOWNLOADS_FOLDER = os.path.expanduser("~/Downloads")

print("🔹 Script started: Setting up UI")

# Resolve UI Setup
ui = fusion.UIManager
dispatcher = bmd.UIDispatcher(ui)

# UI Elements
winID = "com.blackmagicdesign.resolve.SoundEffectInput"
textID = "SoundEffectText"
genID = "GenerateSound"

# **Close existing window properly before creating a new one**
existing_win = ui.FindWindow(winID)
if existing_win:
    print("🔹 Closing existing UI window before recreating...")
    existing_win.Hide()
    dispatcher.ExitLoop()

print("🔹 Creating new UI window for user input")

# Define UI layout
win = dispatcher.AddWindow({
    'ID': winID,
    'Geometry': [100, 100, 400, 200],
    'WindowTitle': "Enter Sound Effect Description",
    },
    ui.VGroup([
        ui.Label({'Text': "Describe your sound effect:"}),
        ui.LineEdit({'ID': textID}),
        ui.Button({'ID': genID, 'Text': "Generate Sound"})
    ])
)


def generate_sound_effect(prompt):
    """Calls ElevenLabs API to generate a sound effect, saves it, moves it, and appends to timeline."""
    print(f"✅ Received user prompt: {prompt}")

    # Replace unsafe characters and format filename
    safe_prompt = prompt.replace(" ", "_").replace("/", "_").replace("\\", "_")

    # Generate a timestamp up to milliseconds
    now = datetime.datetime.now()
    timestamp = now.strftime("%d-%m-%Y_%H-%M-%S-%f")[:-3]  # Trim microseconds to milliseconds

    # Final formatted filename
    formatted_filename = f"{safe_prompt}_{timestamp}.mp3"
    sound_file_path = os.path.join(DOWNLOADS_FOLDER, formatted_filename)

    payload = {
        "text": prompt,
        "output_format": "mp3_44100_128",
        "duration_seconds": None,
        "prompt_influence": 0.3
    }
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    print("🔹 Sending request to text2sound API...")
    response = requests.post(ELEVENLABS_URL, json=payload, headers=headers)

    print(f"🔹 Response Status: {response.status_code}")
    print(f"🔹 Headers: {response.headers}")

    if response.status_code == 200 and response.headers.get("Content-Type", "").startswith("audio"):
        try:
            # Save the raw MP3 file
            with open(sound_file_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Sound file successfully saved at: {sound_file_path}")

            # Move file to project media folder & append to timeline
            project_folder, media_pool, project = get_project_media_folder(resolve)
            final_file_path = move_file_to_media_pool(sound_file_path, project_folder)
            import_and_append_to_timeline(media_pool, project, final_file_path)

        except Exception as e:
            print(f"❌ Error saving file: {e}")

    else:
        print(f"❌ API Error {response.status_code}: {response.text}")

    # Keep UI open
    print("🔹 Ready for next prompt.")

# Event Handler for button click
def OnGenerate(ev):
    """Handles clicking the 'Generate Sound' button."""
    prompt = win.Find(textID).Text.strip()

    if not prompt:
        print("⚠️ No prompt entered. Exiting.")
        return

    print("✅ User input received. Submitting to API...")
    generate_sound_effect(prompt)

# Properly handle closing
def OnClose(ev):
    """Ensures proper cleanup when window is closed manually."""
    print("🔹 Window closed by user.")
    win.Hide()
    dispatcher.ExitLoop()

# Assign event handlers
win.On[genID].Clicked = OnGenerate
win.On[winID].Close = OnClose

print("🔹 Showing UI window")
# Show UI
win.Show()
dispatcher.RunLoop()