""" --- boilerplate code --- """
#!/usr/bin/env python
resolve = app.GetResolve()  # type: ignore - `app` is a davinci native variable
fusion = resolve.Fusion()
""" --- end of boilerplate code --- """

import os
import time
import shutil
import requests
import base64
from dotenv import load_dotenv
from utils import get_project_media_folder, import_and_append_to_timeline, move_file_to_media_pool
load_dotenv()

API_KEY = "luma-6130c11a-162c-45fb-a9d9-f75e11e4ab26-a3ce4a8d-0bfc-4fb8-aaf1-1c3e3a87cbdc"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Resolve UI setup
ui = fusion.UIManager
dispatcher = bmd.UIDispatcher(ui)

winID = "com.blackmagicdesign.resolve.TransitionPrompt"
textID = "TransitionPromptText"
createID = "CreateTransition"

existing_win = ui.FindWindow(winID)
if existing_win:
    existing_win.Hide()
    dispatcher.ExitLoop()

print("🔹 Creating prompt window for user input")

win = dispatcher.AddWindow({
    'ID': winID,
    'Geometry': [100, 100, 400, 200],
    'WindowTitle': "Describe Your Transition (optional)",
}, ui.VGroup([
    ui.Label({'Text': "Enter a prompt for the video transition:"}),
    ui.LineEdit({'ID': textID}),
    ui.Button({'ID': createID, 'Text': "Create Transition"})
]))

def export_frame(frame, output_path):
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline()
    fps = int(project.GetSetting("timelineFrameRate") or 24)
    hh = frame // (3600 * fps)
    mm = (frame % (3600 * fps)) // (60 * fps)
    ss = (frame % (60 * fps)) // fps
    ff = frame % fps
    timecode = f"{hh:02}:{mm:02}:{ss:02}:{ff:02}"
    print(f"🕰️ Setting timecode to {timecode}")
    timeline.SetCurrentTimecode(timecode)
    success = project.ExportCurrentFrameAsStill(output_path)
    if not success or not os.path.exists(output_path):
        raise FileNotFoundError(f"❌ Still image export failed or file not created: {output_path}")
    print(f"📸 Exported frame to {output_path}")
    return output_path

def get_adjacent_clips():
    timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
    item = timeline.GetCurrentVideoItem()
    if item is None:
        raise RuntimeError("❌ No video clip found under the playhead. Make sure the playhead is placed over a clip on the Edit page.")
    playhead_frame = item.GetStart()
    print(f"ℹ️ Playhead is over a clip starting at frame {playhead_frame}")
    for track_index in range(1, timeline.GetTrackCount("video") + 1):
        clips = timeline.GetItemListInTrack("video", track_index)
        clips = [c for c in clips if c is not None]
        clips.sort(key=lambda c: c.GetStart())
        for i, clip in enumerate(clips):
            if clip.GetStart() == item.GetStart() and i < len(clips) - 1:
                return clip, clips[i + 1]
    raise ValueError("❌ Could not find adjacent clip after the one under playhead.")

def upload_image_to_tmpbin(image_path):
    with open(image_path, "rb") as f:
        image_data = f.read()
    res = requests.post("https://tmpfiles.org/api/v1/upload",
                        files={"file": (os.path.basename(image_path), image_data)})
    res.raise_for_status()
    original_url = res.json()["data"]["url"]
    return original_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

def create_generation(prompt, keyframes):
    url = "https://api.lumalabs.ai/dream-machine/v1/generations"
    payload = {
        "prompt": prompt,
        "keyframes": keyframes,
        "aspect_ratio": "16:9",
        "loop": False
    }
    import json
    print("Payload being sent to Luma API:", json.dumps(payload, indent=2))

    res = requests.post(url, json=payload, headers=HEADERS)
    if res.status_code != 201:
        print("❌ Response content:")
        print(res.text)
        print("❌ Response headers:")
        print(res.headers)

    res.raise_for_status()
    return res.json()["id"]

def poll_generation(generation_id):
    url = f"https://api.lumalabs.ai/dream-machine/v1/generations/{generation_id}"
    while True:
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        state = data["state"]
        print(f"Status: {state}")
        if state == "completed":
            return data.get("assets", {}).get("video")
        elif state == "failed":
            raise RuntimeError(f"Generation failed: {data.get('failure_reason')}")
        time.sleep(5)

def generate_transition(prompt):
    print("🔹 Starting transition generator")
    downloads = os.path.expanduser("~/Downloads")
    timestamp = int(time.time())
    frame1_path = os.path.join(downloads, f"frame0_{timestamp}.jpg")
    frame2_path = os.path.join(downloads, f"frame1_{timestamp}.jpg")
    clip1, clip2 = get_adjacent_clips()
    export_frame(clip1.GetEnd() - 1, frame1_path)
    export_frame(clip2.GetStart(), frame2_path)
    url1 = upload_image_to_tmpbin(frame1_path)
    url2 = upload_image_to_tmpbin(frame2_path)
    print("✅ Uploaded keyframes")
    print(f"🖼️ frame0 URL: {url1}")
    print(f"🖼️ frame1 URL: {url2}")
    keyframes = {
        "frame0": {"type": "image", "url": url1},
        "frame1": {"type": "image", "url": url2}
    }
    print("🎞 Creating generation request...")
    gen_id = create_generation(prompt, keyframes)
    video_url = poll_generation(gen_id)
    video_filename = f"transition_{gen_id}.mp4"
    download_path = os.path.join(downloads, video_filename)
    print("⬇️ Downloading generated transition video...")
    video_data = requests.get(video_url)
    with open(download_path, "wb") as f:
        f.write(video_data.content)
    print(f"📥 Video downloaded to: {download_path}")
    project_folder, media_pool, project = get_project_media_folder(resolve)
    final_video_path = move_file_to_media_pool(download_path, project_folder)
    import_and_append_to_timeline(media_pool, project, final_video_path)
    print("✅ Inserted transition into timeline.")

def OnGenerate(ev):
    prompt = win.Find(textID).Text.strip()
    if not prompt:
        prompt = "A smooth cinematic transition"
        print("⚠️ No prompt entered. Using default:", prompt)
    else:
        print("✅ User input received:", prompt)

    generate_transition(prompt)

def OnClose(ev):
    win.Hide()
    dispatcher.ExitLoop()

win.On[createID].Clicked = OnGenerate
win.On[winID].Close = OnClose

print("🔹 Showing transition prompt window")
win.Show()
dispatcher.RunLoop()
