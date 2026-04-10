import asyncio
from typing import List, Callable, Any

from .exceptions import DownloadCancelled


class QueueManager:
    def __init__(self, max_workers: int = 5, cancel_event=None):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        self.cancel_event = cancel_event

    async def download_batch(self, download_func: Callable, items: List[Any]) -> List[Any]:
        async def _download_wrapper(item):
            async with self.semaphore:
                if self.cancel_event and self.cancel_event.is_set():
                    raise DownloadCancelled("下载已取消")
                try:
                    return await download_func(item)
                except DownloadCancelled:
                    raise
                except Exception as e:
                    print(f"Download failed for item: {e}")
                    return {'status': 'error', 'error': str(e), 'item': item}

        tasks = [asyncio.create_task(_download_wrapper(item)) for item in items]
        try:
            return await asyncio.gather(*tasks, return_exceptions=False)
        except DownloadCancelled:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
