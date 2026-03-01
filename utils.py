import os
import subprocess
import asyncio
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI, APIError
import json





def process_video(input_path: str, output_path: str, fps: int = 2, target_height: int = 720) -> None:
    """
    Downsamples video framerate and resolution using ffmpeg.
    """
    # ffmpeg -i input -vf "fps=1,scale=-1:720" output
    cmd = [
        "ffmpeg",
        "-y", # overwrite
        "-i", input_path,
        "-vf", f"fps={fps},scale=-2:min'({target_height},ih)'", # scale=-2 ensures divisibility by 2 for codex compatibility
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",
        output_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr.decode()}")
        raise RuntimeError(f"FFmpeg failed processing {input_path}")


def get_video_info(input_path: str) -> Dict[str, Any]:
    """
    Extracts video metadata (width, height, frame_count) using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_frames,duration,avg_frame_rate",
        "-of", "json",
        input_path
    ]
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        info = json.loads(result.stdout)
        stream = info.get("streams", [{}])[0]
        
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        
        # nb_frames might not be available in all containers, estimate from duration * fps if needed
        nb_frames = stream.get("nb_frames")
        if not nb_frames:
             duration = float(stream.get("duration", 0))
             avg_frame_rate = stream.get("avg_frame_rate", "0/0")
             if "/" in avg_frame_rate:
                 num, den = map(int, avg_frame_rate.split("/"))
                 fps = num / den if den else 0
             else:
                 fps = float(avg_frame_rate)
             nb_frames = int(duration * fps)
        else:
            nb_frames = int(nb_frames)
            
        return {"width": width, "height": height, "frames": nb_frames}
    except Exception as e:
        print(f"FFprobe error: {e}")
        return {"width": 0, "height": 0, "frames": 0}


def extract_frames(input_path: str) -> List[str]:
    """
    Extracts frames from video as base64 encoded strings.
    """
    # Create temp directory for frames
    import tempfile
    import shutil
    
    frames = []
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract frames
        # fps=1 is already done in process_video, but let's be safe or just dump all
        # If input is already processed, it has low fps.
        # Let's just dump all frames.
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-f", "image2",
            os.path.join(temp_dir, "frame_%04d.jpg")
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Read frames
            for filename in sorted(os.listdir(temp_dir)):
                if filename.endswith(".jpg"):
                    with open(os.path.join(temp_dir, filename), "rb") as f:
                        data = f.read()
                        b64 = base64.b64encode(data).decode("utf-8")
                        frames.append(f"data:image/jpeg;base64,{b64}")
                        
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg frame extraction error: {e.stderr.decode()}")
            
    return frames

async def call_vllm_cosmos(
    vllm_url: str,
    prompt: str,
    thinking: bool = False,
    media_paths: Optional[List[str]] = None,
    media_type: Optional[str] = None
) -> str:
    """
    Sends request to VLLM using OpenAI compatible API.
    Supports list of media_paths.
    """
    # Adjust URL to be a base URL for OpenAI client
    # If URL ends with /chat/completions, strip it
    base_url = vllm_url
    if "/chat/completions" in base_url:
        base_url = base_url.split("/chat/completions")[0]
        
    client = AsyncOpenAI(api_key="EMPTY", base_url=base_url)
    
    content = []
    
    # Normalize inputs to a list
    final_media_paths = []
    if media_paths:
        final_media_paths.extend(media_paths)

        
    # Deduplicate if needed, but let's just process what we have
    print(f"Processing {len(final_media_paths)} media items. Type: {media_type}")
    
    if final_media_paths and media_type:
        if media_type == "image":
            for m_path in final_media_paths:
                # Check if local file
                if os.path.exists(m_path):
                    with open(m_path, "rb") as f:
                        data = f.read()
                        b64_data = base64.b64encode(data).decode("utf-8")
                        mime_type = "image/jpeg" 
                        if m_path.lower().endswith(".png"):
                            mime_type = "image/png"
                        
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
                        })
                else:
                    # Assume URL
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": m_path}
                    })
        elif media_type == "video":
            # For video, we usually only handle one video file at a time due to potential size/complexity
            # But let's just iterate if multiple are passed (though likely Recamera uses 'image' mode for bursts)
            for m_path in final_media_paths:
                # Extract frames and send as sequence of images
                # media_path must be a local file path for this to work efficiently
                if os.path.exists(m_path):
                     frames = await asyncio.to_thread(extract_frames, m_path)
                     print(f"Extracted {len(frames)} frames from {m_path}")
                     for frame_b64 in frames:
                         content.append({
                             "type": "image_url",
                             "image_url": {"url": frame_b64} # base64 data uri
                         })
                else:
                    # If it's a URL, we can't easily extract frames without downloading.
                    print(f"Warning: Video path {m_path} not found locally. Cannot extract frames.")
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": m_path}
                    })

    content.append({"type": "text", "text": prompt})

    if thinking:
        content.append({
            "type":"text",
            "text": """Answer the question using the following format:
                <think>
                Your reasoning.
                </think>

                Write your final answer immediately after the </think> tag.
            """
        })
    
    messages = [
        {
            "role": "user",
            "content": content
        }
    ]
    
    try:
        completion = await client.chat.completions.create(
            model="nvidia/Cosmos-Reason2-8B", 
            messages=messages,
            max_tokens=3000
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"VLLM call error: {e}")
        return {"error": str(e), "details": str(type(e))}


async def call_vllm_translate(
    vllm_url: str,
    prompt: str
) -> str:
    """
    Dedicated function to call the translation service (text-only).
    """
    # Adjust URL to be a base URL for OpenAI client
    base_url = vllm_url
    if "/chat/completions" in base_url:
        base_url = base_url.split("/chat/completions")[0]
        
    client = AsyncOpenAI(api_key="EMPTY", base_url=base_url)
    translate_english_to_tamil_prefix = "<<<source>>>en<<<target>>>ta<<<text>>> Translate using informal Tanglish that is spoken in Chennai (i.e tamil mixed with English):  \n"
    messages = [
        {
            "role": "user",
            "content": translate_english_to_tamil_prefix + prompt 
        }
    ]
    
    try:
        completion = await client.chat.completions.create(
            model="Infomaniak-AI/vllm-translategemma-12b-it",
            messages=messages,
            max_tokens=1500,
            temperature=0.5,
            top_p=0.7,
        )
        # If the word chennai is detected, the translation is not good (contains the instruction). Recursively call this function
        if completion.choices[0].message.content.find("சென்னை") != -1:
            return await call_vllm_translate(vllm_url, prompt)
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Translation service error: {e}")
        return {"error": str(e), "details": str(type(e))}


async def call_gemma(url: str, prompt: str) -> str:
    """
    Sends request to Gemma using OpenAI compatible API.
    """
    # Adjust URL to be a base URL for OpenAI client
    base_url = url
    if "/chat/completions" in base_url:
        base_url = base_url.split("/chat/completions")[0]
        
    client = AsyncOpenAI(api_key="EMPTY", base_url=base_url)
    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    try:
        completion = await client.chat.completions.create(
            model="gemma3:27b",
            messages=messages,
            max_tokens=1500,
            response_format={"type": "json_object"},
            temperature=0.9,
            top_p=0.9,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Gemma call error: {e}")
        return f"Error: {e}"
