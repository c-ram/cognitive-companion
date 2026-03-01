import asyncio
from typing import Dict, List, Optional
from workflow import process_event
from minio_utils import minio_client

async def process_event_wrapper(sensor_id, media_paths):
    try:
        await process_event(sensor_id, media_paths)
    except Exception as e:
        print(f"Error processing aggregated event: {e}")
    finally:
        # Cleanup media from MinIO
        if media_paths:
            for url in media_paths:
                object_name = minio_client.extract_object_name(url)
                if object_name:
                    await asyncio.to_thread(minio_client.delete_object, object_name)

# Event Aggregator Logic
class EventAggregator:
    def __init__(self, batch_size=3, window_seconds=10, cooldown_seconds=60):
        self.batch_size = batch_size
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.buffers: Dict[str, List[str]] = {} # sensor_id -> list of media_paths
        self.timers: Dict[str, asyncio.Task] = {} # sensor_id -> timer task
        self.cooldowns: Dict[str, float] = {} # sensor_id -> cooldown end timestamp

    async def add_event(self, sensor_id: str, media_path: str):
        now = asyncio.get_running_loop().time()
        
        # 1. Check Cooldown
        if sensor_id in self.cooldowns:
            if now < self.cooldowns[sensor_id]:
                print(f"Event for {sensor_id} ignored due to cooldown. Now: {now}, Cooldown End: {self.cooldowns[sensor_id]}")
                # Drop event and cleanup immediatey
                if media_path:
                    object_name = minio_client.extract_object_name(media_path)
                    if object_name:
                        await asyncio.to_thread(minio_client.delete_object, object_name)
                return # Drop event
            else:
                del self.cooldowns[sensor_id]

        # 2. Add to Buffer
        if sensor_id not in self.buffers:
            self.buffers[sensor_id] = []
            # Start timer for this new batch
            self.timers[sensor_id] = asyncio.create_task(self.flush_timer(sensor_id))

        if media_path:
             self.buffers[sensor_id].append(media_path)
        
        print(f"Aggregator: {sensor_id} buffer size {len(self.buffers[sensor_id])}")

        # 3. Check Batch Size
        if len(self.buffers[sensor_id]) >= self.batch_size:
            await self.flush(sensor_id)

    async def flush_timer(self, sensor_id: str):
        try:
            await asyncio.sleep(self.window_seconds)
            await self.flush(sensor_id)
        except asyncio.CancelledError:
            pass

    async def flush(self, sensor_id: str):
        if sensor_id not in self.buffers:
            return

        # Cancel timer if running
        if sensor_id in self.timers:
            self.timers[sensor_id].cancel()
            del self.timers[sensor_id]

        media_paths = self.buffers.pop(sensor_id)
        
        if not media_paths:
             return

        print(f"Flushing {len(media_paths)} events for {sensor_id}")
        
        # Start Cooldown
        self.cooldowns[sensor_id] = asyncio.get_running_loop().time() + self.cooldown_seconds
        
        # Trigger processing (fire and forget / background)
        # We need to run this in background, but we are inside an async method.
        # Ideally we use a background task manager or just spawn a task.
        # Since we don't have access to the request's background_tasks cleanly here without passing it around,
        # we can use asyncio.create_task.
        asyncio.create_task(process_event_wrapper(sensor_id, media_paths))
