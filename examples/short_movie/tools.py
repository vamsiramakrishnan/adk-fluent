"""Tool functions for Short Movie Agents.

These tools call Vertex AI Imagen and Veo APIs. In production, they require
GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_BUCKET_NAME environment variables.

Note: The original ADK sample uses ToolContext as an additional parameter to
access session_id and bucket_name from the invocation context. These stubs
simplify the signature for demonstration purposes.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)


def storyboard_generate(prompt: str, scene_number: int) -> list[str]:
    """Generate a storyboard image for a scene using Vertex AI Imagen.

    Args:
        prompt: Text prompt describing the storyboard image.
        scene_number: Scene number for file naming.

    Returns:
        List of GCS URIs for generated images.
    """
    # In production, this calls Vertex AI Imagen 4.0 Ultra:
    #   from vertexai.preview.vision_models import ImageGenerationModel
    #   model = ImageGenerationModel.from_pretrained("imagen-4.0-generate-001")
    #   response = model.generate_images(prompt=prompt, ...)
    #   image.save(location=gcs_uri, include_generation_parameters=False)
    # Requires: vertexai, google-cloud-aiplatform
    logger.info(f"Generating storyboard for scene {scene_number}: {prompt[:80]}...")
    return [f"https://storage.example.com/scene_{scene_number}_storyboard.png"]


def video_generate(
    prompt: str, scene_number: int, image_link: str, screenplay: str
) -> list[str]:
    """Generate a video clip for a scene using Veo 3.0.

    Args:
        prompt: Text prompt describing the video content.
        scene_number: Scene number for file naming.
        image_link: GCS link to the storyboard image.
        screenplay: Full screenplay text for the scene (used for audio/dialogue).

    Returns:
        List of GCS URIs for generated videos.
    """
    # In production, this calls Google GenAI Veo 3.0:
    #   from google import genai
    #   client = genai.Client(vertexai=True, project=project, location=location)
    #   operation = client.models.generate_videos(
    #       model="veo-3.0-generate-preview",
    #       prompt=prompt,
    #       image=Image(image_uri=image_link, mime_type="image/png"),
    #       config=GenerateVideosConfig(...)
    #   )
    #   # Poll until complete, then download video from operation.result
    # Requires: google-genai client with vertexai=True
    logger.info(f"Generating video for scene {scene_number}: {prompt[:80]}...")
    return [f"https://storage.example.com/scene_{scene_number}_video.mp4"]
