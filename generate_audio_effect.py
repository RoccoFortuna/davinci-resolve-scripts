"""
This script generates a sound effect based on user input using the ElevenLabs API and adds it to the timeline.
"""

""" --- boilerplate code --- """
#!/usr/bin/env python
resolve = app.GetResolve()  # `app` is a davinci native variable
fusion = resolve.Fusion()
""" --- end of boilerplate code --- """

import os
import requests
import base64
import shutil

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

def get_project_media_folder():
    """
    Get the directory of an existing media file in the Media Pool.
    This is used as the inferred project folder.
    """
    print("🔹 Detecting project media folder...")

    # Get Project Manager
    project_manager = resolve.GetProjectManager()

    # Get Current Project
    project = project_manager.GetCurrentProject()
    if not project:
        raise RuntimeError("❌ No active project found.")

    # Get Media Pool
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    # Find any existing media file that is not the timeline
    media_file = None
    for item in root_folder.GetClipList():
        if item.GetClipProperty()["File Name"] != "Timeline 1":
            media_file = item
            break

    if media_file is None:
        raise RuntimeError("❌ No media files found in the Media Pool other than Timeline 1.")

    media_file_path = media_file.GetClipProperty("File Path")
    project_media_folder = os.path.dirname(media_file_path)

    print(f"✅ Detected project media folder: {project_media_folder}")
    return project_media_folder, media_pool, project

def move_file_to_media_pool(src_file, dest_folder):
    """
    Moves the given file to the media pool folder.
    """
    print("🔹 Moving generated sound file to project media folder...")
    if not os.path.exists(src_file):
        raise FileNotFoundError(f"❌ File not found: {src_file}")

    dest_file_path = os.path.join(dest_folder, os.path.basename(src_file))
    shutil.move(src_file, dest_file_path)
    print(f"✅ Moved file to project media folder: {dest_file_path}")
    return dest_file_path

def import_and_append_to_timeline(media_pool, project, file_path):
    """
    Imports the given file into the Media Pool and appends it to the timeline.
    """
    print("🔹 Importing sound file into Media Pool...")
    imported_clips = media_pool.ImportMedia([file_path])
    if not imported_clips:
        raise RuntimeError("❌ Failed to import media.")

    # Append to timeline
    media_pool.AppendToTimeline(imported_clips)
    print("✅ Sound effect successfully added to the timeline.")

def generate_sound_effect(prompt):
    """Calls ElevenLabs API to generate a sound effect, saves it, moves it, and appends to timeline."""
    print(f"✅ Received user prompt: {prompt}")  # Print user input

    # Format filename from prompt
    formatted_filename = prompt.replace(" ", "_") + ".mp3"
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
            project_folder, media_pool, project = get_project_media_folder()
            final_file_path = move_file_to_media_pool(sound_file_path, project_folder)
            import_and_append_to_timeline(media_pool, project, final_file_path)

        except Exception as e:
            print(f"❌ Error saving file: {e}")

    else:
        print(f"❌ API Error {response.status_code}: {response.text}")

    # Keep the UI open, clear input for new prompt
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
win.On[winID].Close = OnClose  # Ensure it properly closes

print("🔹 Showing UI window")
# Show UI
win.Show()
dispatcher.RunLoop()
