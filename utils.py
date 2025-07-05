from pathlib import Path
from dotenv import load_dotenv
import sys
import os
import shutil


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
