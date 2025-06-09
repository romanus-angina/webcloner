import asyncio
import httpx
import hashlib
from pathlib import Path
from typing import List, Dict, Any

from ..models.dom_extraction import ExtractedAssetModel
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AssetDownloaderService:
    """
    Handles downloading of external web assets (images, fonts, etc.)
    concurrently and saving them locally.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.output_dir = Path(settings.temp_storage_path) / "assets" / self.session_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)

    async def download_assets(self, assets: List[ExtractedAssetModel]) -> List[Dict[str, Any]]:
        """
        Downloads all external assets for a given session.

        Args:
            assets: A list of extracted asset models.

        Returns:
            A list of dictionaries with download results, including a
            mapping from the original URL to the new local path.
        """
        tasks = []
        for asset in assets:
            # We only download assets with a URL. Inline content (like SVGs) is skipped.
            if asset.url and asset.asset_type == 'image':
                tasks.append(self._download_single_asset(asset))

        download_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_downloads = []
        for result in download_results:
            if isinstance(result, dict):
                successful_downloads.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Asset download failed: {result}")
        
        logger.info(f"Successfully downloaded {len(successful_downloads)} of {len(tasks)} assets for session {self.session_id}")
        return successful_downloads

    async def _download_single_asset(self, asset: ExtractedAssetModel) -> Dict[str, Any]:
        """
        Downloads a single asset and saves it locally.
        """
        try:
            # Generate a safe, unique filename based on the URL hash
            url_hash = hashlib.md5(asset.url.encode()).hexdigest()
            file_extension = Path(asset.url).suffix or '.jpg' # Default extension
            local_filename = f"{url_hash}{file_extension}"
            local_path = self.output_dir / local_filename

            # Download the asset
            response = await self.client.get(asset.url)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            # Save the content to the local file
            with open(local_path, "wb") as f:
                f.write(response.content)

            logger.debug(f"Saved asset {asset.url} to {local_path}")

            # Create a web-accessible path instead of a file system path
            web_path = f"/static/assets/{self.session_id}/{local_filename}"

            return {
                "original_url": asset.url,
                "local_path": web_path,
                "success": True
            }
        except Exception as e:
            logger.warning(f"Failed to download asset {asset.url}: {e}")
            # We will re-raise to have it caught by asyncio.gather
            raise e

    async def close(self):
        """Closes the HTTP client."""
        await self.client.aclose()