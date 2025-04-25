""" --- boilerplate code --- """
#!/usr/bin/env python
resolve = app.GetResolve()  # type: ignore - `app` is a davinci native variable
fusion = resolve.Fusion()
""" --- end of boilerplate code --- """

import os
import time
import shutil
import requests
import tempfile
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

def export_frame(frame, output_path):
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline()

    # Convert frame number to timecode
    fps = int(project.GetSetting("timelineFrameRate") or 24)
    hh = frame // (3600 * fps)
    mm = (frame % (3600 * fps)) // (60 * fps)
    ss = (frame % (60 * fps)) // fps
    ff = frame % fps
    timecode = f"{hh:02}:{mm:02}:{ss:02}:{ff:02}"

    print(f"🕰️ Setting timecode to {timecode}")
    timeline.SetCurrentTimecode(timecode)

    # Try exporting using ExportCurrentFrameAsStill
    success = project.ExportCurrentFrameAsStill(output_path)
    if not success or not os.path.exists(output_path):
        raise FileNotFoundError(f"❌ Still image export failed or file not created: {output_path}")

    print(f"📸 Exported frame to {output_path}")
    return output_path

def get_adjacent_clips():
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline()

    item = timeline.GetCurrentVideoItem()
    if item is None:
        raise RuntimeError("❌ No video clip found under the playhead. Make sure the playhead is placed over a clip on the Edit page.")
    playhead_frame = item.GetStart()
    print(f"ℹ️ Playhead is over a clip starting at frame {playhead_frame}")

    # Find all clips on the same track
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

    # Original URL (e.g. https://tmpfiles.org/25585755/frame0.jpg)
    original_url = res.json()["data"]["url"]

    # Convert to direct file download URL
    direct_link = original_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

    return direct_link


def create_generation(prompt, keyframes):
    """
    Creates a video generation task using the Luma API.
    """
    url = "https://api.lumalabs.ai/dream-machine/v1/generations"
    payload = {
        "prompt": prompt,
        "keyframes": keyframes,
        "aspect_ratio": "16:9",
        "loop": False
    }
    res = requests.post(url, json=payload, headers=HEADERS)
    res.raise_for_status()
    return res.json()["id"]

def poll_generation(generation_id):
    """
    Polls the generation task until completion and returns the video URL.
    """
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

def insert_video_clip(project, media_pool, video_path, insert_timecode):
    """
    Inserts the generated video clip into the timeline at the specified timecode.
    """
    imported = media_pool.ImportMedia([video_path])
    if not imported:
        raise RuntimeError("Failed to import generated transition clip.")
    media_pool.AppendToTimeline(imported)
    timeline = project.GetCurrentTimeline()
    timeline.SetCurrentTimecode(insert_timecode)

def main():
    print("🔹 Starting transition generator")

    project = resolve.GetProjectManager().GetCurrentProject()
    media_pool = project.GetMediaPool()
    timeline = project.GetCurrentTimeline()

    downloads = os.path.expanduser("~/Downloads")
    timestamp = int(time.time())

    frame1_path = os.path.join(downloads, f"frame0_{timestamp}.jpg")
    frame2_path = os.path.join(downloads, f"frame1_{timestamp}.jpg")

    clip1, clip2 = get_adjacent_clips()
    end1 = clip1.GetEnd()
    start2 = clip2.GetStart()

    export_frame(end1 - 1, frame1_path)
    export_frame(start2, frame2_path)

    url1 = upload_image_to_tmpbin(frame1_path)
    url2 = upload_image_to_tmpbin(frame2_path)

    print("✅ Uploaded keyframes")
    print(f"🖼️ frame0 URL: {url1}")
    print(f"🖼️ frame1 URL: {url2}")

    prompt = "A seamless cinematic transition"
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

    # Move and insert into timeline
    project_folder, media_pool, project = get_project_media_folder(resolve)
    final_video_path = move_file_to_media_pool(download_path, project_folder)
    import_and_append_to_timeline(media_pool, project, final_video_path)


    print("✅ Inserted transition into timeline.")

    # Optional: open Downloads folder
    # os.system("open ~/Downloads")


if __name__ == "__main__":
    main()