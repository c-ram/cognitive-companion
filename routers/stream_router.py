import uuid
import asyncio
import logging
from fastapi import APIRouter, WebSocket
from pathlib import Path

from config import settings
from utils import process_video, call_vllm_cosmos
from minio_utils import minio_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["stream"])

@router.websocket("/analyze_stream")
async def analyze_stream_ws(websocket: WebSocket):
    await websocket.accept()
    request_id = uuid.uuid4().hex
    input_video_path = settings.TEMP_DIR / f"{request_id}.mp4"
    processed_path = settings.TEMP_DIR / f"{request_id}_proc.mp4"

    try:
        with open(input_video_path, "wb") as f:
            while True:
                message = await websocket.receive()
                if message.get("bytes"):
                    f.write(message["bytes"])
                elif message.get("text") == "DONE":
                    break
        
        await asyncio.to_thread(process_video, str(input_video_path), str(processed_path))
        
        # Upload for persistence if needed, but we use local path for VLLM
        object_name = f"{request_id}_proc.mp4"
        await asyncio.to_thread(minio_client.upload_file, str(processed_path), object_name)
             
        response = await call_vllm_cosmos(
            settings.VLLM_COSMOS_URL, 
            "Analyze video stream.", 
            media_path=str(processed_path), 
            media_type="video"
        )
        
        asyncio.create_task(asyncio.to_thread(minio_client.delete_object, object_name))

        await websocket.send_json(response)
        await websocket.close()
        
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass
    finally:
        for p in [input_video_path, processed_path]:
            if p.exists():
                try: p.unlink()
                except: pass
