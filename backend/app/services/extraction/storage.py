# backend/app/services/extraction/storage.py

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from ...config import settings
from ...core.exceptions import ProcessingError
from ...models.dom_extraction import DOMExtractionResultModel, ExtractedElementModel, ExtractedAssetModel
from ...utils.logger import get_logger

logger = get_logger(__name__)

async def save_extraction_result(
    result: DOMExtractionResultModel,
    output_format: str = "json"
) -> str:
    """
    Save extraction result to file.
    
    Args:
        result: DOM extraction result
        output_format: Output format ('json', 'html')
        
    Returns:
        Path to saved file
    """
    output_dir = Path(settings.temp_storage_path) / "extractions"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = int(result.timestamp)
    filename = f"{result.session_id}_extraction_{timestamp}.{output_format}"
    file_path = output_dir / filename
    
    try:
        if output_format == "json":
            # Convert to JSON-serializable format
            data = result.model_dump()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                
        elif output_format == "html":
            # Generate HTML report
            html_content = _generate_html_report(result)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        logger.info(f"Extraction result saved to {file_path}")
        return str(file_path)
        
    except Exception as e:
        logger.error(f"Error saving extraction result: {str(e)}")
        raise ProcessingError(f"Failed to save extraction result: {str(e)}")

def _generate_html_report(result: DOMExtractionResultModel) -> str:
    """Generate HTML report from extraction result."""
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DOM Extraction Report - {result.url}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
            .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
            .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            .element {{ background: #f9f9f9; margin: 10px 0; padding: 10px; border-left: 3px solid #007cba; }}
            .styles {{ font-family: monospace; background: #f0f0f0; padding: 5px; margin: 5px 0; }}
            .color-palette {{ display: flex; flex-wrap: wrap; gap: 10px; }}
            .color-sample {{ width: 50px; height: 50px; border: 1px solid #ccc; border-radius: 3px; }}
            .asset {{ background: #fff3cd; padding: 8px; margin: 5px 0; border-radius: 3px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .success {{ color: #155724; background-color: #d4edda; padding: 5px; border-radius: 3px; }}
            .error {{ color: #721c24; background-color: #f8d7da; padding: 5px; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>DOM Extraction Report</h1>
            <p><strong>URL:</strong> {result.url}</p>
            <p><strong>Session ID:</strong> {result.session_id}</p>
            <p><strong>Extraction Time:</strong> {result.extraction_time:.2f} seconds</p>
            <p><strong>Status:</strong> 
                <span class="{'success' if result.success else 'error'}">
                    {'Success' if result.success else 'Failed'}
                </span>
            </p>
            {f'<p><strong>Error:</strong> {result.error_message}</p>' if result.error_message else ''}
        </div>

        <div class="section">
            <h2>Page Structure</h2>
            <table>
                <tr><th>Property</th><th>Value</th></tr>
                <tr><td>Title</td><td>{result.page_structure.title or 'N/A'}</td></tr>
                <tr><td>Description</td><td>{result.page_structure.meta_description or 'N/A'}</td></tr>
                <tr><td>Language</td><td>{result.page_structure.lang or 'N/A'}</td></tr>
                <tr><td>Charset</td><td>{result.page_structure.charset or 'N/A'}</td></tr>
                <tr><td>Viewport</td><td>{result.page_structure.viewport or 'N/A'}</td></tr>
            </table>
        </div>

        <div class="section">
            <h2>Extraction Summary</h2>
            <table>
                <tr><th>Metric</th><th>Count</th></tr>
                <tr><td>Total Elements</td><td>{result.total_elements}</td></tr>
                <tr><td>Total Stylesheets</td><td>{result.total_stylesheets}</td></tr>
                <tr><td>Total Assets</td><td>{result.total_assets}</td></tr>
                <tr><td>DOM Depth</td><td>{result.dom_depth}</td></tr>
            </table>
        </div>

        <div class="section">
            <h2>Color Palette</h2>
            <div class="color-palette">
                {_generate_color_samples(result.color_palette)}
            </div>
        </div>

        <div class="section">
            <h2>Font Families</h2>
            <ul>
                {chr(10).join(f'<li>{font}</li>' for font in result.font_families[:20])}
            </ul>
        </div>

        <div class="section">
            <h2>Responsive Breakpoints</h2>
            <p>{', '.join(map(str, result.responsive_breakpoints))} px</p>
        </div>

        <div class="section">
            <h2>Top Elements ({min(len(result.elements), 50)} of {len(result.elements)})</h2>
            {_generate_elements_html(result.elements[:50])}
        </div>

        <div class="section">
            <h2>Assets ({len(result.assets)})</h2>
            {_generate_assets_html(result.assets[:100])}
        </div>

    </body>
    </html>
    """
    return html

def _generate_color_samples(colors: List[str]) -> str:
    """Generate HTML for color palette samples."""
    samples = []
    for color in colors[:20]:  # Limit to 20 colors
        color_value = color
        if color.startswith('rgb'):
            color_value = color
        elif not color.startswith('#'):
            color_value = f'#{color}' if len(color) == 6 else color
        
        samples.append(
            f'<div class="color-sample" style="background-color: {color_value};" '
            f'title="{color}"></div>'
        )
    return ''.join(samples)

def _generate_elements_html(elements: List[ExtractedElementModel]) -> str:
    """Generate HTML for elements display."""
    elements_html = []
    for element in elements:
        styles_text = '; '.join(f'{k}: {v}' for k, v in list(element.computed_styles.items())[:10])
        
        element_html = f"""
        <div class="element">
            <strong>{element.tag_name}</strong>
            {f'#{element.element_id}' if element.element_id else ''}
            {f'.{" .".join(element.class_names[:3])}' if element.class_names else ''}
            <br>
            <small>Children: {element.children_count} | Visible: {element.is_visible}</small>
            {f'<div class="styles">{styles_text}...</div>' if styles_text else ''}
        </div>
        """
        elements_html.append(element_html)
    
    return ''.join(elements_html)

def _generate_assets_html(assets: List[ExtractedAssetModel]) -> str:
    """Generate HTML for assets display."""
    assets_html = []
    for asset in assets:
        asset_html = f"""
        <div class="asset">
            <strong>{asset.asset_type.upper()}</strong>: 
            <a href="{asset.url}" target="_blank">{asset.url[:100]}...</a>
            {f'<br><small>Alt: {asset.alt_text}</small>' if asset.alt_text else ''}
            {f'<br><small>Dimensions: {asset.dimensions[0]}x{asset.dimensions[1]}</small>' if asset.dimensions else ''}
            <br><small>Context: {', '.join(asset.usage_context)}</small>
        </div>
        """
        assets_html.append(asset_html)
    
    return ''.join(assets_html)

async def get_extraction_info(session_id: str) -> Dict[str, Any]:
    """
    Get information about extractions for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Dictionary with extraction information
    """
    extractions_dir = Path(settings.temp_storage_path) / "extractions"
    
    if not extractions_dir.exists():
        return {"session_id": session_id, "extractions": []}
    
    extraction_files = list(extractions_dir.glob(f"{session_id}_extraction_*.json"))
    
    extractions_info = []
    total_size = 0
    
    for file_path in extraction_files:
        try:
            stat = file_path.stat()
            info = {
                "filename": file_path.name,
                "size": stat.st_size,
                "created": stat.st_mtime,
                "path": str(file_path)
            }
            
            extractions_info.append(info)
            total_size += stat.st_size
            
        except Exception as e:
            logger.warning(f"Error getting info for {file_path.name}: {str(e)}")
    
    return {
        "session_id": session_id,
        "extraction_count": len(extractions_info),
        "total_size": total_size,
        "extractions": extractions_info
    }

async def cleanup_extractions(
    session_id: Optional[str] = None,
    older_than_hours: Optional[int] = None
) -> int:
    """
    Clean up extraction files.
    
    Args:
        session_id: Clean up specific session (if None, cleans all)
        older_than_hours: Only clean files older than this many hours
        
    Returns:
        Number of files cleaned up
    """
    extractions_dir = Path(settings.temp_storage_path) / "extractions"
    
    if not extractions_dir.exists():
        return 0
    
    cleaned_count = 0
    current_time = time.time()
    
    pattern = f"{session_id}_extraction_*.json" if session_id else "*.json"
    
    for file_path in extractions_dir.glob(pattern):
        # Check age filter
        if older_than_hours:
            file_age_hours = (current_time - file_path.stat().st_mtime) / 3600
            if file_age_hours < older_than_hours:
                continue
        
        try:
            file_path.unlink()
            cleaned_count += 1
            logger.debug(f"Cleaned up extraction: {file_path.name}")
        except Exception as e:
            logger.warning(f"Failed to clean up {file_path.name}: {str(e)}")
    
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} extraction files")
    
    return cleaned_count