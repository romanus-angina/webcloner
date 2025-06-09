# backend/app/services/extraction/analyzer.py

from typing import Dict, Any

from ...models.dom_extraction import DOMExtractionResultModel

async def analyze_page_complexity(result: DOMExtractionResultModel) -> Dict[str, Any]:
    """
    Analyze page complexity based on extraction results.
    
    Args:
        result: DOM extraction result
        
    Returns:
        Complexity analysis metrics
    """
    if not result.success:
        return {"error": "Cannot analyze failed extraction"}
    
    complexity = {
        "overall_score": 0,
        "dom_complexity": 0,
        "style_complexity": 0,
        "asset_complexity": 0,
        "layout_complexity": 0,
        "recommendations": []
    }
    
    # DOM complexity (0-100)
    dom_score = min(100, (result.total_elements / 10) + (result.dom_depth * 5))
    complexity["dom_complexity"] = dom_score
    
    # Style complexity (0-100)
    total_rules = sum(len(sheet.rules) for sheet in result.stylesheets)
    style_score = min(100, (total_rules / 5) + (len(result.stylesheets) * 10))
    complexity["style_complexity"] = style_score
    
    # Asset complexity (0-100)
    asset_score = min(100, result.total_assets * 2)
    complexity["asset_complexity"] = asset_score
    
    # Layout complexity (0-100)
    layout_score = 0
    if result.layout_analysis.get("layoutType") == "grid":
        layout_score += 30
    elif result.layout_analysis.get("layoutType") == "flex":
        layout_score += 20
    
    layout_score += min(50, len(result.responsive_breakpoints) * 10)
    layout_score += min(20, len(result.color_palette))
    complexity["layout_complexity"] = layout_score
    
    # Overall complexity
    complexity["overall_score"] = (dom_score + style_score + asset_score + layout_score) / 4
    
    # Generate recommendations
    if dom_score > 80:
        complexity["recommendations"].append("High DOM complexity - consider element reduction")
    if style_score > 80:
        complexity["recommendations"].append("High style complexity - consider CSS optimization")
    if asset_score > 80:
        complexity["recommendations"].append("High asset count - consider asset optimization")
    if len(result.color_palette) > 15:
        complexity["recommendations"].append("Large color palette - consider color consolidation")
    
    return complexity