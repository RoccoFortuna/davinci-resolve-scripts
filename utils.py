from pathlib import Path
from dotenv import load_dotenv
import sys
import os
import shutil
import requests


def get_project_media_folder(resolve):
    """
    Get the directory of an existing media file in the Media Pool.
    This is used as the inferred project folder.
    """
    print("🔹 Detecting project media folder...")

    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    if not project:
        raise RuntimeError("❌ No active project found.")

    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    media_file = None
    for item in root_folder.GetClipList():
        if item.GetClipProperty("File Name") != "Timeline 1":
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
    print("🔹 Moving generated file to project media folder...")
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
    print("🔹 Importing file into Media Pool...")
    imported_clips = media_pool.ImportMedia([file_path])
    if not imported_clips:
        raise RuntimeError("❌ Failed to import media.")

    media_pool.AppendToTimeline(imported_clips)
    print("✅ Media successfully added to the timeline.")


def load_env():
    """
    Loads .env file from the same directory as the script,
    or uses the current working directory as fallback.
    Makes env vars available via os.getenv.
    """
    script_path = Path(sys.argv[0]).resolve()
    script_dir = script_path.parent

    if not script_path.exists():
        print("sys.argv[0] empty or invalid, using CWD")
        script_dir = Path.cwd()

    env_path = script_dir / ".env"
    load_dotenv(dotenv_path=env_path)

    print(f"✅ Loaded .env from: {env_path}")
    print(f"CWD: {os.getcwd()}")


def upload_file_to_tmpbin(file_path):
    """
    Uploads a file (image or video) to tmpfiles.org temporary hosting.
    Returns a direct download URL.

    Args:
        file_path (str): Path to file to upload

    Returns:
        str: Direct download URL for the uploaded file

    Raises:
        requests.HTTPError: If upload fails
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ File not found: {file_path}")

    print(f"🔹 Uploading file to temporary hosting: {os.path.basename(file_path)}")

    with open(file_path, "rb") as f:
        file_data = f.read()

    response = requests.post(
        "https://tmpfiles.org/api/v1/upload",
        files={"file": (os.path.basename(file_path), file_data)}
    )
    response.raise_for_status()

    # Convert tmpfiles.org URL to direct download URL with HTTPS
    original_url = response.json()["data"]["url"]
    download_url = original_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

    # Ensure HTTPS (required by Grok API)
    if download_url.startswith("http://"):
        download_url = download_url.replace("http://", "https://", 1)

    print(f"✅ File uploaded successfully")
    print(f"🔗 URL: {download_url}")

    return download_url


def get_clip_duration_seconds(clip, fps):
    """
    Calculate clip duration in seconds

    Args:
        clip: DaVinci Resolve clip object
        fps (float): Timeline frame rate

    Returns:
        float: Duration in seconds
    """
    start_frame = clip.GetStart()
    end_frame = clip.GetEnd()
    duration_frames = end_frame - start_frame
    duration_seconds = duration_frames / fps

    return duration_seconds


def validate_clip_for_grok(clip, fps, max_duration=8.7):
    """
    Validate if clip meets Grok API constraints (max 8.7 seconds)

    Args:
        clip: DaVinci Resolve clip object
        fps (float): Timeline frame rate
        max_duration (float): Maximum allowed duration in seconds

    Returns:
        tuple: (bool, float, str) - (is_valid, duration_seconds, message)
    """
    duration = get_clip_duration_seconds(clip, fps)

    if duration > max_duration:
        message = (
            f"⚠️ Clip duration ({duration:.2f}s) exceeds Grok's maximum ({max_duration}s). "
            f"Please trim the clip or select a shorter segment."
        )
        return False, duration, message

    return True, duration, f"✅ Clip duration: {duration:.2f}s (valid)"


def get_video_duration(video_path):
    """
    Get video duration in seconds using ffprobe

    Args:
        video_path (str): Path to video file

    Returns:
        float: Duration in seconds, or None if unable to determine
    """
    try:
        import subprocess

        # Try common ffprobe locations
        ffprobe_paths = [
            '/opt/homebrew/bin/ffprobe',  # Homebrew on Apple Silicon
            '/usr/local/bin/ffprobe',      # Homebrew on Intel Mac
            'ffprobe'                       # In PATH
        ]

        for ffprobe in ffprobe_paths:
            try:
                result = subprocess.run(
                    [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return float(result.stdout.strip())
            except FileNotFoundError:
                continue  # Try next path

    except (subprocess.TimeoutExpired, ValueError, Exception) as e:
        print(f"⚠️ Could not determine video duration: {e}")
    return None
