""" --- boilerplate code --- """
#!/usr/bin/env python
resolve = app.GetResolve()  # type: ignore - `app` is a davinci native variable
fusion = resolve.Fusion()
""" --- end of boilerplate code --- """

import os
import time
import shutil
from utils import (
    load_env,
    get_project_media_folder,
    import_and_append_to_timeline,
    move_file_to_media_pool,
    upload_file_to_tmpbin,
    validate_clip_for_grok,
    get_video_duration
)
from grok_api import create_grok_client

load_env()

# Initialize Grok client (validates API key)
grok = create_grok_client()

# Resolve UI setup
ui = fusion.UIManager
dispatcher = bmd.UIDispatcher(ui)  # type: ignore - `bmd` is a davinci native variable

winID = "com.blackmagicdesign.resolve.VideoEditPrompt"
textID = "VideoEditPromptText"
editID = "EditVideo"
aspectRatioID = "AspectRatioCombo"
resolutionID = "ResolutionCombo"

# Close any existing window
existing_win = ui.FindWindow(winID)
if existing_win:
    existing_win.Hide()
    dispatcher.ExitLoop()


def export_clip_as_video(project, timeline, clip, output_path):
    """
    Export a timeline clip as MP4 video using DaVinci's render queue

    Args:
        project: DaVinci Resolve project object
        timeline: Timeline object
        clip: Clip object to export
        output_path: Destination path for exported video

    Returns:
        str: Path to exported video

    Raises:
        RuntimeError: If export fails
    """
    print(f"🎬 Exporting clip to video: {os.path.basename(output_path)}")

    # Save current page to restore after render
    current_page = resolve.GetCurrentPage()
    print(f"💾 Current page: {current_page}")

    # Get clip boundaries
    clip_start = clip.GetStart()
    clip_end = clip.GetEnd()

    # Get FPS
    fps = int(project.GetSetting("timelineFrameRate") or 24)

    # Convert frame numbers to timecode
    def frames_to_timecode(frame):
        hh = frame // (3600 * fps)
        mm = (frame % (3600 * fps)) // (60 * fps)
        ss = (frame % (60 * fps)) // fps
        ff = frame % fps
        return f"{hh:02}:{mm:02}:{ss:02}:{ff:02}"

    in_tc = frames_to_timecode(clip_start)
    out_tc = frames_to_timecode(clip_end - 1)

    print(f"📍 Exporting {clip_end - clip_start} frames ({in_tc} to {out_tc})")

    # Prepare render settings
    output_dir = os.path.dirname(output_path)
    output_filename = os.path.splitext(os.path.basename(output_path))[0]

    # Configure render settings for H.264 MP4
    project.SetRenderSettings({
        "SelectAllFrames": False,
        "MarkIn": clip_start,
        "MarkOut": clip_end - 1,
        "TargetDir": output_dir,
        "CustomName": output_filename,
        "ExportVideo": True,
        "ExportAudio": True,
    })

    # Set render format to MP4
    project.SetCurrentRenderFormatAndCodec("MP4", "H264")

    # Add to render queue
    render_job_id = project.AddRenderJob()

    if not render_job_id:
        raise RuntimeError("❌ Failed to add render job to queue")

    # Start rendering
    project.StartRendering(render_job_id)

    # Poll render status
    print("🔄 Rendering clip...")
    max_wait = 300  # 5 minutes timeout
    elapsed = 0

    while elapsed < max_wait:
        status = project.GetRenderJobStatus(render_job_id)

        if status.get("JobStatus") == "Complete":
            print("✅ Render completed successfully")

            # Verify file exists
            expected_path = os.path.join(output_dir, f"{output_filename}.mp4")
            if os.path.exists(expected_path):
                # Rename to exact output path if needed
                if expected_path != output_path:
                    shutil.move(expected_path, output_path)
                print(f"📹 Exported: {output_path}")

                # Restore original page
                resolve.OpenPage(current_page)

                return output_path
            else:
                raise RuntimeError(f"❌ Render completed but file not found: {expected_path}")

        elif status.get("JobStatus") == "Failed":
            error = status.get("Error", "Unknown error")
            resolve.OpenPage(current_page)  # Restore page on error
            raise RuntimeError(f"❌ Render failed: {error}")

        elif status.get("JobStatus") == "Cancelled":
            resolve.OpenPage(current_page)  # Restore page on cancel
            raise RuntimeError("❌ Render was cancelled")

        # Still rendering - poll every 1s, log every 10s
        time.sleep(1)
        elapsed += 1

        if elapsed - last_log >= 10:
            completion = status.get("CompletionPercentage", 0)
            print(f"⏳ Rendering: {completion}%")
            last_log = elapsed

    resolve.OpenPage(current_page)  # Restore page on timeout
    raise RuntimeError(f"❌ Render timeout after {max_wait} seconds")


def edit_video_with_grok(prompt, aspect_ratio, resolution):
    """
    Main workflow for video editing with Grok API

    Args:
        prompt (str): Text description of desired edits
        aspect_ratio (str): Target aspect ratio
        resolution (str): Target resolution
    """
    print("🔹 Starting Grok video editor")

    # Get current project and timeline
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    if not project:
        raise RuntimeError("❌ No active project found")

    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("❌ No active timeline found")

    # Get selected clip
    clip = timeline.GetCurrentVideoItem()
    if not clip:
        raise RuntimeError(
            "❌ No video clip selected. Please position the playhead over a clip on the timeline."
        )

    clip_name = clip.GetName()
    print(f"🎬 Selected clip: {clip_name}")

    # Validate clip duration (max 8.7 seconds for Grok API)
    fps = float(project.GetSetting("timelineFrameRate") or 24)
    is_valid, duration, message = validate_clip_for_grok(clip, fps)

    if not is_valid:
        raise ValueError(message)

    print(f"✅ Clip: {duration:.2f}s")

    # Export clip to temporary video file
    downloads = os.path.expanduser("~/Downloads")
    timestamp = int(time.time())
    temp_video_path = os.path.join(downloads, f"temp_clip_{timestamp}.mp4")

    try:
        export_clip_as_video(project, timeline, clip, temp_video_path)
    except Exception as e:
        print(f"❌ Export failed: {e}")
        print("💡 Alternative: Please manually export the clip and use image-to-video instead")
        raise

    # Upload video to temporary hosting
    video_url = upload_file_to_tmpbin(temp_video_path)

    # Submit to Grok API
    print(f"🤖 Submitting to Grok API...")
    print(f"📝 Prompt: {prompt}")

    request_id = grok.generate_video(
        prompt=prompt,
        video_url=video_url,
        aspect_ratio=aspect_ratio if aspect_ratio != "Original" else None,
        resolution=resolution if resolution != "Original" else None
    )

    # Poll for completion (poll every 1s, log every 10s)
    result = grok.poll_until_complete(request_id, poll_interval=1, max_attempts=600, log_interval=10)

    # Download edited video
    edited_video_url = result["url"]
    edited_video_filename = f"grok_edited_{timestamp}.mp4"
    edited_video_path = os.path.join(downloads, edited_video_filename)

    grok.download_video(edited_video_url, edited_video_path)

    # Clean up temporary file
    if os.path.exists(temp_video_path):
        os.remove(temp_video_path)

    # Import to project
    project_folder, media_pool, project = get_project_media_folder(resolve)
    final_video_path = move_file_to_media_pool(edited_video_path, project_folder)
    import_and_append_to_timeline(media_pool, project, final_video_path)

    print(f"✅ Complete! Edited clip added to timeline")
    print(f"📁 Saved to: {final_video_path}")


# Create UI window
print("🔹 Creating video edit prompt window")

win = dispatcher.AddWindow({
    'ID': winID,
    'Geometry': [100, 100, 500, 280],
    'WindowTitle': "Edit Video Clip with AI",
}, ui.VGroup([
    ui.Label({'Text': "Describe how you want to transform the video:", 'WordWrap': True}),
    ui.Label({'Text': "(e.g., 'Add dramatic sunset lighting', 'Make it look like noir film')", 'StyleSheet': 'font-size: 10px; color: #888;'}),
    ui.LineEdit({'ID': textID, 'PlaceholderText': 'Enter editing instructions...'}),
    ui.HGroup([
        ui.Label({'Text': "Aspect Ratio:"}),
        ui.ComboBox({
            'ID': aspectRatioID,
            'Text': 'Original',
        }),
    ]),
    ui.HGroup([
        ui.Label({'Text': "Resolution:"}),
        ui.ComboBox({
            'ID': resolutionID,
            'Text': 'Original',
        }),
    ]),
    ui.Button({'ID': editID, 'Text': "Transform Video"})
]))

# Populate dropdowns
aspect_combo = win.Find(aspectRatioID)
aspect_combo.AddItem("Original")
aspect_combo.AddItems(["16:9", "4:3", "1:1", "9:16", "3:4", "3:2", "2:3"])

resolution_combo = win.Find(resolutionID)
resolution_combo.AddItem("Original")
resolution_combo.AddItems(["720p", "480p"])


def OnEdit(ev):
    """Handle edit button click"""
    prompt = win.Find(textID).Text.strip()

    if not prompt:
        print("⚠️ No prompt entered. Please describe the desired transformation.")
        return

    aspect_ratio = win.Find(aspectRatioID).CurrentText
    resolution = win.Find(resolutionID).CurrentText

    print(f"✅ Edit request:")
    print(f"   Prompt: {prompt}")
    print(f"   Aspect Ratio: {aspect_ratio}")
    print(f"   Resolution: {resolution}")

    try:
        edit_video_with_grok(prompt, aspect_ratio, resolution)
        print("🎉 Video editing complete!")

        # Close window on success
        win.Hide()
        dispatcher.ExitLoop()

    except Exception as e:
        print(f"❌ Error during video editing: {e}")
        import traceback
        traceback.print_exc()


def OnClose(ev):
    """Handle window close"""
    win.Hide()
    dispatcher.ExitLoop()


# Connect event handlers
win.On[editID].Clicked = OnEdit
win.On[winID].Close = OnClose

print("🔹 Showing video edit prompt window")
win.Show()
dispatcher.RunLoop()
