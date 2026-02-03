# davinci-resolve-scripts
AI-powered scripts for DaVinci Resolve - Generate videos, audio, transitions, and transform clips using AI.


## First Setup
1. Open davinci resolve
2. Open `Workspace -> Console`. Click on `Py3`. A popup will open prompting installation of python. Click on the link. Then in the web page click on the yellow button to install Python.
3. Follow customized installation, tick pip installation and adding to path.

To get the scripts in Davinci:
1. [install git](https://git-scm.com/downloads)
2. Clone this repository in: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit` with these commands:
```
cd "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"
git clone git@github.com:RoccoFortuna/davinci-resolve-scripts.git .
```
3. Install Python dependencies:
```
pip install requests python-dotenv
```
4. Configure API keys (see below)
5. Restart davinci, done!

## API Setup

Create a `.env` file in the scripts directory with your API keys:

```bash
# Luma Labs API (for video transitions)
# Get your key: https://lumalabs.ai/api/keys
LUMA_API_KEY=your_luma_key_here

# ElevenLabs API (for audio effects)
# Get your key: https://elevenlabs.io/app/settings/api-keys
ELEVENLABS_API_KEY=your_elevenlabs_key_here

# Grok API (for video generation and editing)
# Get your key: https://console.x.ai
GROK_API_KEY=your_grok_key_here
```

You can use `.env.template` as a reference.

## Running scripts
To run scripts you've added to the scripts directory, on Davinci head to `Workspace -> Scripts` and click on the script to run it ✅

## Available Scripts

### 🎬 Video Generation & Editing (Grok AI)

#### `edit_video_clip.py` - Transform Video Clips
Transform existing video clips using AI-powered editing.

**Features:**
- Select any clip on the timeline (max 8.7 seconds)
- Describe the transformation you want (e.g., "Add dramatic sunset lighting", "Convert to noir style")
- Customize aspect ratio and resolution
- Automatically imports edited video to timeline

**How to use:**
1. Position playhead over a clip on the timeline
2. Run the script from `Workspace -> Scripts -> edit_video_clip`
3. Enter your editing instructions in the prompt window
4. Click "Transform Video"
5. Wait for processing (typically 30-90 seconds)
6. Edited video will be added to your timeline

**Requirements:**
- Clip must be 8.7 seconds or shorter
- GROK_API_KEY must be set in .env

---

### 🎞️ Video Transitions (Luma Labs)

#### `generate_transition.py` - AI Video Transitions
Generate smooth AI-powered transitions between adjacent clips.

**How to use:**
1. Position playhead between two adjacent clips
2. Run the script
3. Optionally describe the transition style
4. Generated transition is inserted into timeline

**Requirements:** LUMA_API_KEY in .env

---

### 🔊 Audio Effects (ElevenLabs)

#### `generate_audio_effect.py` - AI Sound Effects
Generate custom sound effects from text descriptions.

**How to use:**
1. Run the script
2. Describe the sound effect you need
3. Generated audio is added to timeline
4. Window stays open for multiple generations

**Requirements:** ELEVENLABS_API_KEY in .env

---

## Troubleshooting

**"API key not found" error:**
- Make sure you've created a `.env` file in the scripts directory
- Verify the API key is on the correct line (no extra spaces)
- Restart DaVinci Resolve after creating/editing .env

**"No clip selected" error (edit_video_clip.py):**
- Make sure the playhead is positioned over a clip
- The clip must be on a video track

**"Clip duration exceeds maximum" error:**
- Grok API has a maximum input video length of 8.7 seconds
- Trim your clip before transforming it

**Render fails:**
- Check that you have write permissions to ~/Downloads
- Ensure project has valid media pool items
- Verify timeline is active

**Import fails:**
- Ensure project folder can be detected (requires at least one media file in project)
- Check file permissions in project folder

## Project Structure

```
.
├── README.md                    # This file
├── .env.template                # API key template
├── .env                         # Your API keys (gitignored)
├── utils.py                     # Shared utilities
├── grok_api.py                  # Grok AI API client
├── generate_transition.py       # Luma Labs transition generator
├── generate_audio_effect.py     # ElevenLabs audio generator
└── edit_video_clip.py          # Grok video editor
```

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.
