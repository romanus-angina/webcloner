import asyncio
import httpx
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import re
from urllib.parse import urljoin, urlparse

from ..models.dom_extraction import ExtractedAssetModel
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AssetDownloaderService:
    """
    Enhanced asset downloader that handles images, SVGs, and creates fallbacks.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.output_dir = Path(settings.temp_storage_path) / "assets" / self.session_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)

    async def download_assets(self, assets: List[ExtractedAssetModel]) -> List[Dict[str, Any]]:
        """
        Downloads all assets and creates fallbacks for failed downloads.
        """
        tasks = []
        inline_assets = []
        
        logger.info(f"Processing {len(assets)} assets for download/handling")
        for asset in assets:
            logger.info(f"Asset: {asset.asset_type}, URL: {getattr(asset, 'url', 'None')}, Content: {bool(getattr(asset, 'content', None))}")
            if hasattr(asset, 'content') and asset.content:
                # Handle inline SVGs
                inline_assets.append(self._handle_inline_asset(asset))
            elif hasattr(asset, 'url') and asset.url:
                # Handle external assets
                tasks.append(self._download_single_asset(asset))

        # Download external assets
        download_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_downloads = []
        failed_downloads = []
        
        # Process download results
        for result in download_results:
            if isinstance(result, dict) and result.get('success'):
                successful_downloads.append(result)
            else:
                # Create fallback for failed downloads
                if isinstance(result, Exception):
                    logger.warning(f"Asset download failed: {result}")
                failed_downloads.append(result)
        
        # Add inline assets
        successful_downloads.extend(inline_assets)
        
        # Create fallbacks for failed downloads
        for i, result in enumerate(download_results):
            if isinstance(result, Exception) or (isinstance(result, dict) and not result.get('success')):
                asset = assets[i] if i < len(assets) else None
                if asset and hasattr(asset, 'url'):
                    fallback = self._create_asset_fallback(asset)
                    if fallback:
                        successful_downloads.append(fallback)
        
        logger.info(f"Asset processing completed: {len(successful_downloads)} total, {len(inline_assets)} inline")
        return successful_downloads

    def _handle_inline_asset(self, asset: ExtractedAssetModel) -> Dict[str, Any]:
        """Handle inline assets like SVGs."""
        try:
            if asset.asset_type == 'svg' and asset.content:
                # Save inline SVG to file for consistency
                asset_id = asset.alt_text or 'inline-svg'
                filename = f"{hashlib.md5(asset.content.encode()).hexdigest()[:8]}.svg"
                local_path = self.output_dir / filename
                
                with open(local_path, "w", encoding='utf-8') as f:
                    f.write(asset.content)
                
                web_path = f"/static/assets/{self.session_id}/{filename}"
                
                return {
                    "original_url": f"inline-svg-{asset_id}",
                    "local_path": web_path,
                    "content": asset.content,
                    "asset_type": "svg",
                    "is_inline": True,
                    "success": True
                }
        except Exception as e:
            logger.warning(f"Failed to handle inline asset: {e}")
        
        return {
            "original_url": "inline-asset",
            "local_path": "",
            "content": asset.content if hasattr(asset, 'content') else "",
            "asset_type": asset.asset_type,
            "success": False
        }

    async def _download_single_asset(self, asset: ExtractedAssetModel) -> Dict[str, Any]:
        """Downloads a single external asset."""
        try:
            url_hash = hashlib.md5(asset.url.encode()).hexdigest()[:8]
            
            # Determine file extension
            parsed_url = urlparse(asset.url)
            path_ext = Path(parsed_url.path).suffix
            
            if asset.asset_type == 'image':
                file_extension = path_ext or '.jpg'
            elif asset.asset_type == 'svg':
                file_extension = '.svg'
            else:
                file_extension = path_ext or '.asset'
            
            local_filename = f"{url_hash}{file_extension}"
            local_path = self.output_dir / local_filename

            # Download the asset
            response = await self.client.get(asset.url)
            response.raise_for_status()

            # Save content
            if asset.asset_type == 'svg' or 'svg' in asset.url.lower():
                # Save SVG as text
                with open(local_path, "w", encoding='utf-8') as f:
                    f.write(response.text)
            else:
                # Save binary content
                with open(local_path, "wb") as f:
                    f.write(response.content)

            web_path = f"/static/assets/{self.session_id}/{local_filename}"

            return {
                "original_url": asset.url,
                "local_path": web_path,
                "asset_type": asset.asset_type,
                "success": True
            }
            
        except Exception as e:
            logger.warning(f"Failed to download asset {asset.url}: {e}")
            return {
                "original_url": asset.url,
                "local_path": "",
                "asset_type": asset.asset_type,
                "success": False,
                "error": str(e)
            }

    def _create_asset_fallback(self, asset: ExtractedAssetModel) -> Dict[str, Any]:
        """Create a fallback for failed asset downloads."""
        try:
            if asset.asset_type == 'image':
                # Create placeholder image data URL
                placeholder_svg = f'''<svg width="200" height="150" xmlns="http://www.w3.org/2000/svg">
                    <rect width="100%" height="100%" fill="#f3f4f6"/>
                    <text x="50%" y="50%" text-anchor="middle" dy="0.3em" fill="#6b7280" font-family="Arial, sans-serif" font-size="14">
                        {asset.alt_text or 'Image'}
                    </text>
                </svg>'''
                
                return {
                    "original_url": asset.url,
                    "local_path": f"data:image/svg+xml;base64,{hashlib.b64encode(placeholder_svg.encode()).decode()}",
                    "asset_type": "image",
                    "is_fallback": True,
                    "success": True
                }
            
            elif asset.asset_type == 'svg':
                # Create simple fallback SVG
                fallback_svg = '''<svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
                    <circle cx="12" cy="12" r="10" fill="#3b82f6"/>
                </svg>'''
                
                return {
                    "original_url": asset.url,
                    "local_path": f"data:image/svg+xml;base64,{hashlib.b64encode(fallback_svg.encode()).decode()}",
                    "asset_type": "svg",
                    "content": fallback_svg,
                    "is_fallback": True,
                    "success": True
                }
                
        except Exception as e:
            logger.warning(f"Failed to create fallback for {asset.url}: {e}")
        
        return None

    async def close(self):
        """Closes the HTTP client."""
        await self.client.aclose()