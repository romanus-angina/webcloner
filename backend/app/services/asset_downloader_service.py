import asyncio
import httpx
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
from urllib.parse import urljoin, urlparse, unquote
import mimetypes
import base64
from io import BytesIO

# Only import PIL if available
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..models.dom_extraction import ExtractedAssetModel
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Keep the original class for backward compatibility
class AssetDownloaderService:
    """
    Enhanced asset downloader that handles images, SVGs, and creates fallbacks.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.output_dir = Path(settings.temp_storage_path) / "assets" / self.session_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Enhanced HTTP client with better headers and timeout handling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        
        self.download_stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'data_urls': 0,
            'inline_content': 0
        }

    async def download_assets(self, assets: List[ExtractedAssetModel]) -> List[Dict[str, Any]]:
        """
        Enhanced asset downloading with better categorization and error handling.
        """
        if not assets:
            logger.info("No assets to process")
            return []
        
        logger.info(f"Processing {len(assets)} assets for download/handling")
        
        # Categorize assets for different processing
        external_assets = []
        data_url_assets = []
        inline_assets = []
        
        for asset in assets:
            if hasattr(asset, 'content') and asset.content:
                inline_assets.append(asset)
            elif hasattr(asset, 'url') and asset.url:
                if asset.url.startswith('data:'):
                    data_url_assets.append(asset)
                elif asset.url.startswith(('http://', 'https://', '//')):
                    external_assets.append(asset)
                else:
                    # Relative URLs - skip for now
                    logger.warning(f"Skipping relative URL: {asset.url}")
            else:
                logger.warning(f"Asset has no URL or content: {asset}")
        
        logger.info(f"Asset categorization: {len(external_assets)} external, {len(data_url_assets)} data URLs, {len(inline_assets)} inline")
        
        # Process different asset types
        results = []
        
        # Process external assets with limited concurrency
        if external_assets:
            semaphore = asyncio.Semaphore(3)  # Limit concurrent downloads
            tasks = [self._download_single_asset_with_semaphore(asset, semaphore) for asset in external_assets]
            external_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in external_results:
                if isinstance(result, Exception):
                    logger.error(f"Download task failed: {result}")
                    self.download_stats['failed'] += 1
                    results.append(self._create_error_result(str(result)))
                else:
                    results.append(result)
        
        # Process data URLs
        for asset in data_url_assets:
            result = await self._handle_data_url_asset(asset)
            results.append(result)
        
        # Process inline content
        for asset in inline_assets:
            result = self._handle_inline_asset(asset)
            results.append(result)
        
        # Create fallbacks for failed downloads
        failed_results = [r for r in results if not r.get('success', False)]
        for failed_result in failed_results:
            original_asset = failed_result.get('original_asset')
            if original_asset:
                fallback = self._create_asset_fallback(original_asset)
                if fallback:
                    results.append(fallback)
        
        # Update stats
        self.download_stats['total'] = len(results)
        self.download_stats['successful'] = len([r for r in results if r.get('success', False)])
        
        logger.info(f"Asset processing completed: {self.download_stats}")
        return results

    async def _download_single_asset_with_semaphore(self, asset: ExtractedAssetModel, semaphore: asyncio.Semaphore):
        """Download single asset with concurrency control."""
        async with semaphore:
            return await self._download_single_asset(asset)

    async def _download_single_asset(self, asset: ExtractedAssetModel) -> Dict[str, Any]:
        """Enhanced single asset download with better error handling."""
        try:
            # Clean and validate URL
            url = self._clean_url(asset.url)
            if not url:
                return self._create_error_result("Invalid URL", asset)
            
            # Generate filename
            filename = self._generate_filename(url, asset)
            local_path = self.output_dir / filename
            
            logger.debug(f"Downloading asset: {url} -> {filename}")
            
            # Download with retries
            content, content_type = await self._download_with_retries(url)
            
            if not content:
                return self._create_error_result("No content received", asset)
            
            # Process content if needed
            processed_content = self._process_asset_content(content, content_type, asset)
            
            # Save to file
            if asset.asset_type == 'svg' or 'svg' in content_type:
                # Save SVG as text
                with open(local_path, "w", encoding='utf-8') as f:
                    if isinstance(processed_content, bytes):
                        f.write(processed_content.decode('utf-8'))
                    else:
                        f.write(processed_content)
            else:
                # Save binary content
                with open(local_path, "wb") as f:
                    if isinstance(processed_content, bytes):
                        f.write(processed_content)
                    else:
                        f.write(processed_content.encode())
            
            web_path = f"/static/assets/{self.session_id}/{filename}"
            
            result = {
                "original_url": asset.url,
                "local_path": web_path,
                "local_file_path": str(local_path),
                "asset_type": asset.asset_type,
                "content_type": content_type,
                "file_size": len(processed_content) if isinstance(processed_content, bytes) else len(processed_content.encode()),
                "success": True,
                "original_asset": asset
            }
            
            self.download_stats['successful'] += 1
            return result
            
        except Exception as e:
            logger.warning(f"Failed to download asset {asset.url}: {e}")
            self.download_stats['failed'] += 1
            return self._create_error_result(str(e), asset)

    async def _download_with_retries(self, url: str, max_retries: int = 3) -> tuple[bytes, str]:
        """Download content with retries."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                
                content_type = response.headers.get('content-type', '').lower()
                return response.content, content_type
                
            except httpx.TimeoutException as e:
                last_error = f"Timeout on attempt {attempt + 1}: {e}"
                logger.warning(last_error)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise  # Don't retry 404s
                last_error = f"HTTP {e.response.status_code} on attempt {attempt + 1}"
                logger.warning(last_error)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    
            except Exception as e:
                last_error = f"Request failed on attempt {attempt + 1}: {e}"
                logger.warning(last_error)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        raise Exception(f"Failed to download after {max_retries} attempts. Last error: {last_error}")

    def _process_asset_content(self, content: bytes, content_type: str, asset: ExtractedAssetModel) -> bytes:
        """Process and validate asset content."""
        try:
            # SVG processing
            if 'svg' in content_type or asset.asset_type == 'svg':
                svg_content = content.decode('utf-8')
                # Basic SVG sanitization
                svg_content = self._sanitize_svg(svg_content)
                return svg_content.encode('utf-8')
            
            # Image processing (only if PIL is available)
            elif PIL_AVAILABLE and (content_type.startswith('image/') or asset.asset_type == 'image'):
                try:
                    img = Image.open(BytesIO(content))
                    
                    # Resize if too large (max 2048px)
                    max_size = 2048
                    if max(img.size) > max_size:
                        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                        
                        # Save back to bytes
                        output = BytesIO()
                        # Convert to RGB if needed for JPEG
                        if img.mode in ('RGBA', 'LA', 'P'):
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            if img.mode in ('RGBA', 'LA'):
                                background.paste(img, mask=img.split()[-1])
                            else:
                                background.paste(img)
                            img = background
                        
                        img.save(output, format='JPEG', quality=85, optimize=True)
                        return output.getvalue()
                    
                except Exception as e:
                    logger.warning(f"Image processing failed: {e}")
                    # Return original content if processing fails
                    pass
            
            return content
            
        except Exception as e:
            logger.warning(f"Content processing failed: {e}")
            return content

    def _sanitize_svg(self, svg_content: str) -> str:
        """Basic SVG sanitization."""
        # Remove script tags and event handlers
        svg_content = re.sub(r'<script[^>]*>.*?</script>', '', svg_content, flags=re.DOTALL | re.IGNORECASE)
        svg_content = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', svg_content, flags=re.IGNORECASE)
        svg_content = re.sub(r'javascript:', '', svg_content, flags=re.IGNORECASE)
        return svg_content

    async def _handle_data_url_asset(self, asset: ExtractedAssetModel) -> Dict[str, Any]:
        """Handle data URL assets."""
        try:
            if not asset.url.startswith('data:'):
                return self._create_error_result("Invalid data URL", asset)
            
            # Extract data from data URL
            header, data = asset.url.split(',', 1)
            mime_type = header.split(';')[0].split(':')[1] if ':' in header else 'application/octet-stream'
            is_base64 = 'base64' in header
            
            # Decode content
            if is_base64:
                content = base64.b64decode(data)
            else:
                content = unquote(data).encode('utf-8')
            
            # Generate filename
            ext = mimetypes.guess_extension(mime_type) or '.bin'
            filename = f"data_{hashlib.md5(asset.url.encode()).hexdigest()[:8]}{ext}"
            local_path = self.output_dir / filename
            
            # Save content
            with open(local_path, "wb") as f:
                f.write(content)
            
            web_path = f"/static/assets/{self.session_id}/{filename}"
            
            self.download_stats['data_urls'] += 1
            
            return {
                "original_url": asset.url,
                "local_path": web_path,
                "local_file_path": str(local_path),
                "asset_type": asset.asset_type,
                "content_type": mime_type,
                "file_size": len(content),
                "is_data_url": True,
                "success": True,
                "original_asset": asset
            }
            
        except Exception as e:
            logger.warning(f"Failed to process data URL: {e}")
            return self._create_error_result(str(e), asset)

    def _handle_inline_asset(self, asset: ExtractedAssetModel) -> Dict[str, Any]:
        """Handle inline assets like SVGs."""
        try:
            if asset.asset_type == 'svg' and asset.content:
                # Clean SVG content
                svg_content = self._sanitize_svg(asset.content)
                
                # Generate filename
                content_hash = hashlib.md5(svg_content.encode()).hexdigest()[:8]
                filename = f"inline_svg_{content_hash}.svg"
                local_path = self.output_dir / filename
                
                # Save SVG
                with open(local_path, "w", encoding='utf-8') as f:
                    f.write(svg_content)
                
                web_path = f"/static/assets/{self.session_id}/{filename}"
                
                self.download_stats['inline_content'] += 1
                
                return {
                    "original_url": f"inline-svg-{getattr(asset, 'alt_text', 'icon')}",
                    "local_path": web_path,
                    "local_file_path": str(local_path),
                    "content": svg_content,
                    "asset_type": "svg",
                    "content_type": "image/svg+xml",
                    "file_size": len(svg_content.encode()),
                    "is_inline": True,
                    "success": True,
                    "original_asset": asset
                }
                
        except Exception as e:
            logger.warning(f"Failed to handle inline asset: {e}")
            return self._create_error_result(str(e), asset)
        
        return self._create_error_result("Unsupported inline asset", asset)

    def _clean_url(self, url: str) -> Optional[str]:
        """Clean and validate URL."""
        if not url:
            return None
        
        # Handle protocol-relative URLs
        if url.startswith('//'):
            url = 'https:' + url
        
        # Handle relative URLs (skip for now)
        if url.startswith('/') and not url.startswith('//'):
            logger.warning(f"Relative URL found, skipping: {url}")
            return None
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://', 'data:')):
            logger.warning(f"Invalid URL scheme: {url}")
            return None
        
        return url

    def _generate_filename(self, url: str, asset: ExtractedAssetModel) -> str:
        """Generate filename with proper extension detection."""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Try to determine extension from URL
        parsed_url = urlparse(url)
        path_ext = Path(parsed_url.path).suffix.lower()
        
        # Extension mapping based on asset type
        type_extensions = {
            'image': '.jpg',
            'svg': '.svg',
            'background-image': '.jpg',
            'video-poster': '.jpg',
            'css-background': '.jpg'
        }
        
        # Use path extension if valid, otherwise use asset type mapping
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp'}
        
        if path_ext in valid_extensions:
            extension = path_ext
        else:
            extension = type_extensions.get(asset.asset_type, '.asset')
        
        return f"{url_hash}_{asset.asset_type}{extension}"

    def _create_error_result(self, error_message: str, asset: Optional[ExtractedAssetModel] = None) -> Dict[str, Any]:
        """Create error result."""
        return {
            "original_url": asset.url if asset else "unknown",
            "local_path": "",
            "asset_type": asset.asset_type if asset else "unknown",
            "success": False,
            "error": error_message,
            "original_asset": asset
        }

    def _create_asset_fallback(self, asset: Optional[ExtractedAssetModel]) -> Optional[Dict[str, Any]]:
        """Create fallback for failed asset downloads."""
        if not asset:
            return None
        
        try:
            import base64
            
            if asset.asset_type == 'image':
                # Create placeholder image
                placeholder_svg = f'''<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">
                    <rect width="100%" height="100%" fill="#f3f4f6" stroke="#d1d5db" stroke-width="2"/>
                    <text x="50%" y="50%" text-anchor="middle" dy="0.3em" fill="#6b7280" 
                          font-family="Arial, sans-serif" font-size="14">
                        {getattr(asset, 'alt_text', 'Image')}
                    </text>
                </svg>'''
                
                return {
                    "original_url": asset.url,
                    "local_path": f"data:image/svg+xml;base64,{base64.b64encode(placeholder_svg.encode()).decode()}",
                    "asset_type": "image",
                    "content_type": "image/svg+xml",
                    "is_fallback": True,
                    "success": True,
                    "original_asset": asset
                }
            
            elif asset.asset_type == 'svg':
                # Create simple fallback SVG
                fallback_svg = '''<svg width="24" height="24" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
                    <circle cx="12" cy="12" r="10" fill="#6b7280"/>
                    <text x="12" y="16" text-anchor="middle" fill="white" font-size="12">?</text>
                </svg>'''
                
                return {
                    "original_url": asset.url,
                    "local_path": f"data:image/svg+xml;base64,{base64.b64encode(fallback_svg.encode()).decode()}",
                    "asset_type": "svg",
                    "content_type": "image/svg+xml",
                    "content": fallback_svg,
                    "is_fallback": True,
                    "success": True,
                    "original_asset": asset
                }
                
        except Exception as e:
            logger.warning(f"Failed to create fallback for {asset.url}: {e}")
        
        return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def get_stats(self) -> Dict[str, Any]:
        """Get download statistics."""
        return self.download_stats.copy()