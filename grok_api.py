"""
Grok Video Generation API Client
Handles video generation and editing using xAI's Grok Imagine API
"""

import os
import time
import requests


class GrokVideoClient:
    """Client for interacting with Grok video generation API"""

    def __init__(self, api_key):
        """
        Initialize Grok API client

        Args:
            api_key (str): Grok API key from environment
        """
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_video(self, prompt, model="grok-imagine-video", duration=None,
                      aspect_ratio=None, resolution=None, image_url=None, video_url=None):
        """
        Submit a video generation or editing request to Grok API

        Args:
            prompt (str): Text description for video generation or editing
            model (str): Model identifier (default: grok-imagine-video)
            duration (int): Video length in seconds (1-15, optional for editing)
            aspect_ratio (str): Video aspect ratio (16:9, 4:3, 1:1, 9:16, 3:4, 3:2, 2:3)
            resolution (str): Output quality (720p, 480p)
            image_url (str): URL for image-to-video generation (optional)
            video_url (str): URL of video to edit (optional, max 8.7s)

        Returns:
            str: Request ID for polling

        Raises:
            requests.HTTPError: If API request fails
        """
        # Video editing uses a different endpoint and payload structure
        if video_url:
            url = f"{self.base_url}/videos/edits"
            payload = {
                "model": model,
                "prompt": prompt,
                "video": {"url": video_url}
            }
            # Note: aspect_ratio and resolution may not be supported for edits
            # Only include if provided
            if aspect_ratio:
                payload["aspect_ratio"] = aspect_ratio
            if resolution:
                payload["resolution"] = resolution
        else:
            # Text-to-video or image-to-video generation
            url = f"{self.base_url}/videos/generations"
            payload = {
                "model": model,
                "prompt": prompt
            }

            # Add optional parameters for generation
            if image_url:
                payload["image_url"] = image_url

            if duration:
                payload["duration"] = duration

            if aspect_ratio:
                payload["aspect_ratio"] = aspect_ratio

            if resolution:
                payload["resolution"] = resolution

        response = requests.post(url, json=payload, headers=self.headers)

        if response.status_code != 200:
            print("❌ API error:", response.status_code)
            print(response.text)

        response.raise_for_status()
        data = response.json()

        request_id = data.get("request_id")
        if not request_id:
            raise ValueError(f"❌ No request_id in response: {data}")

        return request_id

    def get_status(self, request_id):
        """
        Check status of a video generation request

        Args:
            request_id (str): Request ID from generate_video()

        Returns:
            dict: Response data with url, duration, request_id if completed
            None: If still processing

        Raises:
            RuntimeError: If generation failed
            requests.HTTPError: If API request fails
        """
        # Based on xAI SDK pattern: client.video.get(request_id)
        # Try the GET request endpoint
        url = f"{self.base_url}/videos/{request_id}"

        response = requests.get(url, headers=self.headers)

        # If 404, video might still be processing - return None
        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()

        # Check if video is ready (response has "video" object with "url")
        if "video" in data and "url" in data["video"]:
            # Flatten the structure for easier access
            return {
                "url": data["video"]["url"],
                "duration": data["video"].get("duration"),
                "model": data.get("model"),
                "request_id": request_id
            }

        # Check for explicit failure state (if API provides one)
        if data.get("state") == "failed" or data.get("status") == "failed":
            failure_reason = data.get("failure_reason") or data.get("error") or "Unknown error"
            raise RuntimeError(f"❌ Video generation failed: {failure_reason}")

        # Still processing (video object not present yet)
        return None

    def poll_until_complete(self, request_id, poll_interval=1, max_attempts=600, log_interval=10):
        """
        Poll generation status until completion or timeout

        Args:
            request_id (str): Request ID from generate_video()
            poll_interval (int): Seconds between status checks (default: 1)
            max_attempts (int): Maximum polling attempts (default: 600 = 10 minutes)
            log_interval (int): Seconds between log messages (default: 10)

        Returns:
            dict: Completed video data with url, duration, request_id

        Raises:
            TimeoutError: If max_attempts exceeded
            RuntimeError: If generation failed
        """
        print(f"⏳ Waiting for Grok...")

        attempts = 0
        last_log = 0

        while attempts < max_attempts:
            result = self.get_status(request_id)

            if result is not None:
                print("✅ Video generation complete!")
                return result

            attempts += 1
            elapsed = attempts * poll_interval

            # Log progress every log_interval seconds
            if elapsed - last_log >= log_interval:
                print(f"⏳ Still processing... ({elapsed}s)")
                last_log = elapsed

            time.sleep(poll_interval)

        raise TimeoutError(
            f"❌ Video generation timed out after {max_attempts * poll_interval}s. "
            f"Request ID: {request_id}"
        )

    def download_video(self, video_url, output_path):
        """
        Download generated video from URL

        Args:
            video_url (str): URL of generated video
            output_path (str): Local path to save video

        Returns:
            str: Path to downloaded video

        Raises:
            requests.HTTPError: If download fails
        """
        print(f"⬇️ Downloading...")

        response = requests.get(video_url)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"📥 Downloaded")
        return output_path


def create_grok_client():
    """
    Factory function to create Grok client with API key validation

    Returns:
        GrokVideoClient: Initialized client

    Raises:
        ValueError: If GROK_API_KEY not found in environment
    """
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        raise ValueError(
            "GROK_API_KEY missing in environment variables. "
            "Please set it in your .env file."
        )

    return GrokVideoClient(api_key)
