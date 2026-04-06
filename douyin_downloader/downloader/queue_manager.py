
import asyncio
from typing import List, Callable, Any

class QueueManager:
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def download_batch(self, download_func: Callable, items: List[Any]) -> List[Any]:
        async def _download_wrapper(item):
            async with self.semaphore:
                try:
                    return await download_func(item)
                except Exception as e:
                    print(f"Download failed for item: {e}")
                    return {'status': 'error', 'error': str(e), 'item': item}

        results = await asyncio.gather(*[_download_wrapper(item) for item in items], return_exceptions=False)
        return results
