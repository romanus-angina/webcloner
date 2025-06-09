from typing import Dict, List, Optional, Any, Set, Tuple
import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
import time

from ..config import settings
from ..core.exceptions import (
    BrowserError,
    ProcessingError,
    NetworkError
)
from ..utils.logger import get_logger
from .browser_manager import BrowserManager

logger = get_logger(__name__)


@dataclass
class ExtractedElement:
    """Represents an extracted DOM element with computed styles."""
    tag_name: str
    element_id: Optional[str] = None
    class_names: List[str] = None
    computed_styles: Dict[str, str] = None
    attributes: Dict[str, str] = None
    text_content: Optional[str] = None
    children_count: int = 0
    xpath: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    is_visible: bool = True
    z_index: Optional[int] = None
    
    def __post_init__(self):
        if self.class_names is None:
            self.class_names = []
        if self.computed_styles is None:
            self.computed_styles = {}
        if self.attributes is None:
            self.attributes = {}


@dataclass
class ExtractedStylesheet:
    """Represents an extracted stylesheet."""
    href: Optional[str] = None
    media: str = "all"
    rules: List[Dict[str, Any]] = None
    inline: bool = False
    content: Optional[str] = None
    critical: bool = False
    cors_blocked: bool = False
    
    def __post_init__(self):
        if self.rules is None:
            self.rules = []


@dataclass
class ExtractedAsset:
    """Represents an extracted asset (image, font, etc.)."""
    url: str
    asset_type: str  # 'image', 'font', 'video', 'audio', 'icon'
    mime_type: Optional[str] = None
    size: Optional[int] = None
    dimensions: Optional[Tuple[int, int]] = None
    alt_text: Optional[str] = None
    is_background: bool = False
    usage_context: List[str] = None
    
    def __post_init__(self):
        if self.usage_context is None:
            self.usage_context = []


@dataclass
class PageStructure:
    """Represents the overall page structure and metadata."""
    title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    lang: Optional[str] = None
    charset: Optional[str] = None
    viewport: Optional[str] = None
    favicon_url: Optional[str] = None
    canonical_url: Optional[str] = None
    open_graph: Dict[str, str] = None
    schema_org: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.open_graph is None:
            self.open_graph = {}
        if self.schema_org is None:
            self.schema_org = []


@dataclass
class DOMExtractionResult:
    """Complete DOM extraction result."""
    url: str
    session_id: str
    timestamp: float
    extraction_time: float
    
    # Core structure
    page_structure: PageStructure
    elements: List[ExtractedElement]
    stylesheets: List[ExtractedStylesheet]
    assets: List[ExtractedAsset]
    
    # Analysis data
    layout_analysis: Dict[str, Any]
    color_palette: List[str]
    font_families: List[str]
    responsive_breakpoints: List[int]
    
    # Technical metrics
    dom_depth: int = 0
    total_elements: int = 0
    total_stylesheets: int = 0
    total_assets: int = 0
    success: bool = True
    error_message: Optional[str] = None


class DOMExtractionService:
    """
    Service for extracting DOM structure, styles, and assets from web pages.
    
    Provides comprehensive analysis of page structure, computed styles,
    layout information, and asset discovery for website cloning.
    """
    
    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager
        self._javascript_extractors = self._load_extraction_scripts()
    
    def _load_extraction_scripts(self) -> Dict[str, str]:
        """Load JavaScript extraction scripts."""
        return {
            "dom_extractor": self._get_dom_extractor_script(),
            "style_extractor": self._get_style_extractor_script(),
            "asset_extractor": self._get_asset_extractor_script(),
            "layout_analyzer": self._get_layout_analyzer_script()
        }

    def _get_dom_extractor_script(self) -> str:
        """Enhanced DOM extraction script that waits for dynamic content."""
        return """
        (() => {
            // Wait for dynamic content to load
            function waitForDynamicContent() {
                return new Promise((resolve) => {
                    let attempts = 0;
                    const maxAttempts = 50; // 10 seconds max wait
                    
                    function checkContent() {
                        attempts++;
                        
                        // Check if page seems fully loaded
                        const hasImages = document.querySelectorAll('img[src]').length > 0;
                        const hasText = document.body.innerText.trim().length > 100;
                        const noLoadingIndicators = document.querySelectorAll('[class*="loading"], [class*="spinner"], [id*="loading"]').length === 0;
                        
                        if ((hasImages || hasText) && noLoadingIndicators) {
                            resolve(true);
                        } else if (attempts >= maxAttempts) {
                            resolve(false); // Timeout
                        } else {
                            setTimeout(checkContent, 200);
                        }
                    }
                    
                    checkContent();
                });
            }
            
            async function extractWithWait() {
                // Wait for dynamic content
                await waitForDynamicContent();
                
                // Additional wait for any remaining animations/renders
                await new Promise(resolve => setTimeout(resolve, 2000));
                
                const elements = [];
                const allNodes = document.querySelectorAll('*');
                
                for (let i = 0; i < allNodes.length; i++) {
                    const element = allNodes[i];
                    
                    try {
                        const tagName = element.tagName.toLowerCase();
                        
                        // Skip script and style tags
                        if (tagName === 'script' || tagName === 'style') {
                            continue;
                        }
                        
                        // Get bounding box for layout analysis
                        const rect = element.getBoundingClientRect();
                        const bounding_box = rect.width > 0 && rect.height > 0 ? {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            top: rect.top,
                            right: rect.right,
                            bottom: rect.bottom,
                            left: rect.left
                        } : null;
                        
                        // Enhanced attribute extraction
                        const attributes = {};
                        if (element.attributes) {
                            for (let j = 0; j < element.attributes.length; j++) {
                                const attr = element.attributes[j];
                                if (attr && attr.name && attr.value !== undefined) {
                                    attributes[attr.name] = attr.value;
                                }
                            }
                        }
                        
                        // Better text content extraction
                        let textContent = '';
                        if (element.childNodes) {
                            for (let k = 0; k < element.childNodes.length; k++) {
                                const node = element.childNodes[k];
                                if (node && node.nodeType === 3 && node.textContent) {
                                    textContent += node.textContent;
                                }
                            }
                        }
                        textContent = textContent.trim();
                        
                        // Enhanced class extraction
                        const classNames = [];
                        if (element.className && typeof element.className === 'string') {
                            const classes = element.className.trim();
                            if (classes) {
                                classNames.push(...classes.split(/\s+/).filter(cls => cls.length > 0));
                            }
                        }
                        
                        // Comprehensive computed styles
                        const computedStyles = {};
                        try {
                            const style = window.getComputedStyle(element);
                            if (style) {
                                // Critical layout properties
                                const criticalProps = [
                                    'display', 'position', 'top', 'right', 'bottom', 'left',
                                    'width', 'height', 'margin', 'padding', 'border',
                                    'background', 'background-color', 'background-image',
                                    'color', 'font-family', 'font-size', 'font-weight',
                                    'text-align', 'text-decoration', 'line-height',
                                    'flex', 'flex-direction', 'justify-content', 'align-items',
                                    'grid', 'grid-template-columns', 'grid-template-rows',
                                    'box-shadow', 'border-radius', 'opacity', 'z-index',
                                    'overflow', 'white-space', 'word-wrap'
                                ];
                                
                                criticalProps.forEach(prop => {
                                    const value = style.getPropertyValue(prop);
                                    if (value && value !== 'initial' && value !== 'normal') {
                                        computedStyles[prop] = value;
                                    }
                                });
                            }
                        } catch (e) {
                            // Fallback styles
                            computedStyles['display'] = 'block';
                        }
                        
                        // Generate XPath for better element identification
                        function getXPath(element) {
                            if (element.id) {
                                return `//*[@id="${element.id}"]`;
                            }
                            
                            const parts = [];
                            let current = element;
                            
                            while (current && current.nodeType === Node.ELEMENT_NODE) {
                                let part = current.tagName.toLowerCase();
                                
                                if (current.className) {
                                    const classes = current.className.trim().split(/\s+/);
                                    if (classes.length > 0) {
                                        part += `[@class="${current.className}"]`;
                                    }
                                }
                                
                                parts.unshift(part);
                                current = current.parentNode;
                                
                                if (parts.length > 10) break; // Prevent overly long XPaths
                            }
                            
                            return '/' + parts.join('/');
                        }
                        
                        const elementData = {
                            tag_name: tagName,
                            element_id: element.id || null,
                            class_names: classNames,
                            computed_styles: computedStyles,
                            attributes: attributes,
                            text_content: textContent || null,
                            children_count: element.children ? element.children.length : 0,
                            xpath: getXPath(element),
                            bounding_box: bounding_box,
                            is_visible: rect.width > 0 && rect.height > 0 && 
                                    style.display !== 'none' && 
                                    style.visibility !== 'hidden',
                            z_index: computedStyles['z-index'] ? parseInt(computedStyles['z-index']) || 0 : 0
                        };
                        
                        elements.push(elementData);
                        
                    } catch (e) {
                        console.warn('Error processing element:', e);
                        continue;
                    }
                }
                
                return {
                    elements: elements,
                    total_elements: elements.length,
                    dom_depth: Math.max(...elements.map(e => (e.xpath?.split('/').length || 0))) - 1,
                    page_fully_loaded: true
                };
            }
            
            return extractWithWait();
        })()
        """
    
    def _get_asset_extractor_script(self) -> str:
        """JavaScript for asset discovery - FIXED version."""
        return """
        (() => {
            function extractAssets() {
                const assets = [];
                const processedUrls = new Set();
                
                function addAsset(url, type, element = null, context = []) {
                    if (!url || processedUrls.has(url)) return;
                    processedUrls.add(url);
                    
                    const asset = {
                        url: url,
                        asset_type: type,  // FIXED: was assetType, now asset_type
                        usage_context: context,
                        is_background: false
                    };
                    
                    if (element) {
                        if (element.alt) asset.alt_text = element.alt;  // FIXED: was altText
                        if (element.naturalWidth && element.naturalHeight) {
                            asset.dimensions = [element.naturalWidth, element.naturalHeight];
                        }
                    }
                    
                    assets.push(asset);
                }
                
                // Extract images
                const images = document.querySelectorAll('img[src]');
                for (let img of images) {
                    addAsset(img.src, 'image', img, ['img-tag']);
                }
                
                // Extract background images from computed styles
                const allElements = document.querySelectorAll('*');
                for (let element of allElements) {
                    try {
                        const style = window.getComputedStyle(element);
                        const bgImage = style.backgroundImage;
                        
                        if (bgImage && bgImage !== 'none') {
                            const urlMatch = bgImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                            if (urlMatch) {
                                const asset = {
                                    url: urlMatch[1],
                                    asset_type: 'image',  // FIXED: was assetType
                                    usage_context: ['background-image'],
                                    is_background: true
                                };
                                
                                if (!processedUrls.has(asset.url)) {
                                    processedUrls.add(asset.url);
                                    assets.push(asset);
                                }
                            }
                        }
                    } catch (e) {
                        // Skip elements that can't be accessed
                    }
                }
                
                // Extract fonts
                try {
                    for (let stylesheet of document.styleSheets) {
                        try {
                            for (let rule of stylesheet.cssRules) {
                                if (rule.type === CSSRule.FONT_FACE_RULE) {
                                    const src = rule.style.src;
                                    if (src) {
                                        const urlMatches = src.match(/url\\(["']?([^"')]+)["']?\\)/g);
                                        if (urlMatches) {
                                            urlMatches.forEach(match => {
                                                const url = match.match(/url\\(["']?([^"')]+)["']?\\)/)[1];
                                                addAsset(url, 'font', null, ['font-face']);
                                            });
                                        }
                                    }
                                }
                            }
                        } catch (e) {
                            // Can't access cross-origin stylesheets
                        }
                    }
                } catch (e) {
                    // StyleSheets access failed
                }
                
                // Extract videos and audio
                try {
                    const videos = document.querySelectorAll('video[src], video source[src]');
                    for (let video of videos) {
                        if (video.src) {
                            addAsset(video.src, 'video', null, ['video-tag']);
                        }
                    }
                    
                    const audios = document.querySelectorAll('audio[src], audio source[src]');
                    for (let audio of audios) {
                        if (audio.src) {
                            addAsset(audio.src, 'audio', null, ['audio-tag']);
                        }
                    }
                } catch (e) {
                    // Media element access failed
                }
                
                // Extract favicons and icons
                try {
                    const icons = document.querySelectorAll('link[rel*="icon"]');
                    for (let icon of icons) {
                        if (icon.href) {
                            addAsset(icon.href, 'icon', null, ['favicon']);
                        }
                    }
                } catch (e) {
                    // Icon extraction failed
                }
                
                return {
                    assets: assets,
                    total_assets: assets.length
                };
            }
            
            return extractAssets();
        })()
        """

    def _get_style_extractor_script(self) -> str:
        """Comprehensive CSS and style extraction that captures actual visual styling."""
        return """
        (() => {
            function extractComprehensiveStyles() {
                const result = {
                    stylesheets: [],
                    computed_styles: {},
                    css_variables: {},
                    theme_colors: {},
                    typography: {},
                    layout_patterns: {},
                    visual_hierarchy: []
                };
                
                // 1. Extract CSS Variables (CSS Custom Properties)
                function extractCSSVariables() {
                    const variables = {};
                    const rootStyles = getComputedStyle(document.documentElement);
                    
                    // Get all CSS custom properties from :root
                    for (let i = 0; i < rootStyles.length; i++) {
                        const property = rootStyles[i];
                        if (property.startsWith('--')) {
                            variables[property] = rootStyles.getPropertyValue(property).trim();
                        }
                    }
                    
                    return variables;
                }
                
                // 2. Analyze Theme Colors (backgrounds, text, etc.)
                function analyzeThemeColors() {
                    const theme = {
                        primary_background: null,
                        secondary_background: null,
                        primary_text: null,
                        secondary_text: null,
                        accent_colors: [],
                        is_dark_theme: false
                    };
                    
                    // Analyze body/html background
                    const bodyStyle = getComputedStyle(document.body);
                    const htmlStyle = getComputedStyle(document.documentElement);
                    
                    theme.primary_background = bodyStyle.backgroundColor || htmlStyle.backgroundColor;
                    theme.primary_text = bodyStyle.color;
                    
                    // Detect dark theme
                    const bgColor = theme.primary_background;
                    if (bgColor && bgColor !== 'rgba(0, 0, 0, 0)') {
                        // Convert to RGB and check brightness
                        const rgbMatch = bgColor.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                        if (rgbMatch) {
                            const [_, r, g, b] = rgbMatch.map(Number);
                            const brightness = (r * 299 + g * 587 + b * 114) / 1000;
                            theme.is_dark_theme = brightness < 128;
                        }
                    }
                    
                    return theme;
                }
                
                // 3. Extract Typography Patterns
                function extractTypography() {
                    const typography = {
                        headings: {},
                        body_text: {},
                        font_families: new Set(),
                        font_weights: new Set(),
                        font_sizes: new Set()
                    };
                    
                    // Analyze headings
                    ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].forEach(tag => {
                        const elements = document.querySelectorAll(tag);
                        if (elements.length > 0) {
                            const firstElement = elements[0];
                            const style = getComputedStyle(firstElement);
                            typography.headings[tag] = {
                                font_family: style.fontFamily,
                                font_size: style.fontSize,
                                font_weight: style.fontWeight,
                                line_height: style.lineHeight,
                                color: style.color,
                                margin: style.margin,
                                text_transform: style.textTransform
                            };
                            
                            typography.font_families.add(style.fontFamily);
                            typography.font_weights.add(style.fontWeight);
                            typography.font_sizes.add(style.fontSize);
                        }
                    });
                    
                    // Analyze body text
                    const bodyStyle = getComputedStyle(document.body);
                    typography.body_text = {
                        font_family: bodyStyle.fontFamily,
                        font_size: bodyStyle.fontSize,
                        font_weight: bodyStyle.fontWeight,
                        line_height: bodyStyle.lineHeight,
                        color: bodyStyle.color
                    };
                    
                    // Convert Sets to Arrays
                    typography.font_families = Array.from(typography.font_families);
                    typography.font_weights = Array.from(typography.font_weights);
                    typography.font_sizes = Array.from(typography.font_sizes);
                    
                    return typography;
                }
                
                // 4. Extract Layout Patterns
                function extractLayoutPatterns() {
                    const patterns = {
                        containers: [],
                        spacing_scale: new Set(),
                        border_radius_scale: new Set(),
                        shadow_patterns: new Set(),
                        grid_systems: [],
                        flex_patterns: []
                    };
                    
                    // Find container elements
                    const containers = document.querySelectorAll('[class*="container"], [class*="wrapper"], [class*="content"]');
                    containers.forEach(container => {
                        const style = getComputedStyle(container);
                        patterns.containers.push({
                            max_width: style.maxWidth,
                            padding: style.padding,
                            margin: style.margin
                        });
                    });
                    
                    // Extract spacing patterns
                    const allElements = document.querySelectorAll('*');
                    for (let i = 0; i < Math.min(allElements.length, 200); i++) {
                        const element = allElements[i];
                        const style = getComputedStyle(element);
                        
                        // Collect spacing values
                        [style.margin, style.padding].forEach(value => {
                            if (value && value !== '0px') {
                                patterns.spacing_scale.add(value);
                            }
                        });
                        
                        // Collect border radius
                        if (style.borderRadius && style.borderRadius !== '0px') {
                            patterns.border_radius_scale.add(style.borderRadius);
                        }
                        
                        // Collect box shadows
                        if (style.boxShadow && style.boxShadow !== 'none') {
                            patterns.shadow_patterns.add(style.boxShadow);
                        }
                        
                        // Detect grid/flex usage
                        if (style.display === 'grid') {
                            patterns.grid_systems.push({
                                grid_template_columns: style.gridTemplateColumns,
                                grid_gap: style.gridGap || style.gap
                            });
                        } else if (style.display === 'flex') {
                            patterns.flex_patterns.push({
                                flex_direction: style.flexDirection,
                                justify_content: style.justifyContent,
                                align_items: style.alignItems,
                                gap: style.gap
                            });
                        }
                    }
                    
                    // Convert Sets to Arrays
                    patterns.spacing_scale = Array.from(patterns.spacing_scale);
                    patterns.border_radius_scale = Array.from(patterns.border_radius_scale);
                    patterns.shadow_patterns = Array.from(patterns.shadow_patterns);
                    
                    return patterns;
                }
                
                // 5. Extract Visual Hierarchy
                function extractVisualHierarchy() {
                    const hierarchy = [];
                    
                    // Find visually prominent elements
                    const prominentSelectors = [
                        'h1', 'h2', 'h3', 
                        '[class*="hero"]', '[class*="banner"]', '[class*="header"]',
                        '[class*="title"]', '[class*="heading"]',
                        'button', '[role="button"]', 'a[class*="btn"]'
                    ];
                    
                    prominentSelectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach((element, index) => {
                            if (index < 5) { // Limit to first 5 of each type
                                const style = getComputedStyle(element);
                                const rect = element.getBoundingClientRect();
                                
                                if (rect.width > 0 && rect.height > 0) {
                                    hierarchy.push({
                                        element_type: selector,
                                        text_content: element.textContent?.slice(0, 100) || '',
                                        styles: {
                                            font_size: style.fontSize,
                                            font_weight: style.fontWeight,
                                            color: style.color,
                                            background_color: style.backgroundColor,
                                            border: style.border,
                                            border_radius: style.borderRadius,
                                            padding: style.padding,
                                            margin: style.margin,
                                            box_shadow: style.boxShadow,
                                            display: style.display,
                                            position: style.position
                                        },
                                        dimensions: {
                                            width: rect.width,
                                            height: rect.height
                                        }
                                    });
                                }
                            }
                        });
                    });
                    
                    return hierarchy;
                }
                
                // 6. Enhanced Stylesheet Extraction
                function extractStylesheets() {
                    const stylesheets = [];
                    
                    // External stylesheets
                    document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
                        const stylesheet = {
                            href: link.href,
                            media: link.media || 'all',
                            inline: false,
                            rules: [],
                            critical: link.href.includes('fonts') || link.media === 'all'
                        };
                        
                        try {
                            if (link.sheet?.cssRules) {
                                Array.from(link.sheet.cssRules).forEach(rule => {
                                    if (rule.type === CSSRule.STYLE_RULE) {
                                        stylesheet.rules.push({
                                            selector: rule.selectorText,
                                            styles: rule.style.cssText,
                                            important: rule.style.cssText.includes('!important')
                                        });
                                    }
                                });
                            }
                        } catch (e) {
                            // CORS blocked - still record the stylesheet
                            stylesheet.cors_blocked = true;
                        }
                        
                        stylesheets.push(stylesheet);
                    });
                    
                    // Inline styles
                    document.querySelectorAll('style').forEach(style => {
                        stylesheets.push({
                            href: null,
                            media: style.media || 'all',
                            inline: true,
                            content: style.textContent,
                            rules: [],
                            critical: true
                        });
                    });
                    
                    return stylesheets;
                }
                
                // Execute all extractions
                result.css_variables = extractCSSVariables();
                result.theme_colors = analyzeThemeColors();
                result.typography = extractTypography();
                result.layout_patterns = extractLayoutPatterns();
                result.visual_hierarchy = extractVisualHierarchy();
                result.stylesheets = extractStylesheets();
                
                return result;
            }
            
            return extractComprehensiveStyles();
        })()
        """

    
    def _get_layout_analyzer_script(self) -> str:
        """Enhanced JavaScript for layout analysis."""
        return """
        (() => {
            function analyzeEnhancedLayout() {
                const analysis = {
                    color_palette: [],
                    font_families: [],
                    responsive_breakpoints: [],
                    layout_type: 'unknown',
                    grid_systems: [],
                    flexbox_usage: 0,
                    css_frameworks: [],
                    spacing_patterns: []
                };
                
                // Extract comprehensive color palette
                const colors = new Set();
                const elements = document.querySelectorAll('*');
                
                for (let element of elements) {
                    try {
                        const style = window.getComputedStyle(element);
                        
                        // Extract all color properties
                        const colorProps = [
                            'color', 'background-color', 'border-color', 
                            'border-top-color', 'border-right-color', 
                            'border-bottom-color', 'border-left-color',
                            'box-shadow', 'text-shadow', 'outline-color'
                        ];
                        
                        colorProps.forEach(prop => {
                            const value = style.getPropertyValue(prop);
                            if (value && value !== 'rgba(0, 0, 0, 0)' && 
                                value !== 'transparent' && value !== 'initial' && 
                                value !== 'inherit' && value !== 'none') {
                                
                                // Extract colors from box-shadow and text-shadow
                                if (prop.includes('shadow') && value !== 'none') {
                                    const shadowColors = value.match(/rgba?\\([^)]+\\)|#[a-fA-F0-9]{3,6}|[a-zA-Z]+/g);
                                    if (shadowColors) {
                                        shadowColors.forEach(color => colors.add(color));
                                    }
                                } else {
                                    colors.add(value);
                                }
                            }
                        });
                        
                        // Extract font families
                        const fontFamily = style.getPropertyValue('font-family');
                        if (fontFamily && fontFamily !== 'initial' && fontFamily !== 'inherit') {
                            const families = fontFamily.split(',').map(f => 
                                f.trim().replace(/['"]/g, '')
                            );
                            families.forEach(family => {
                                if (family && !family.includes('serif') && !family.includes('sans-serif')) {
                                    analysis.font_families.push(family);
                                }
                            });
                        }
                        
                        // Analyze layout patterns
                        const display = style.getPropertyValue('display');
                        if (display === 'flex' || display === 'inline-flex') {
                            analysis.flexbox_usage++;
                        }
                        
                        if (display === 'grid' || display === 'inline-grid') {
                            const gridTemplate = style.getPropertyValue('grid-template-columns') || 
                                            style.getPropertyValue('grid-template-rows');
                            if (gridTemplate && gridTemplate !== 'none') {
                                analysis.grid_systems.push({
                                    element: element.tagName.toLowerCase(),
                                    template: gridTemplate
                                });
                            }
                        }
                        
                        // Check for CSS framework classes
                        const className = element.className;
                        if (typeof className === 'string') {
                            const frameworks = {
                                'bootstrap': /\\b(container|row|col-|btn-|card-|navbar-)/,
                                'tailwind': /\\b(flex|grid|p-|m-|text-|bg-|border-)/,
                                'bulma': /\\b(column|hero|navbar|card|button)/,
                                'foundation': /\\b(row|column|button|callout)/
                            };
                            
                            Object.entries(frameworks).forEach(([framework, pattern]) => {
                                if (pattern.test(className) && !analysis.css_frameworks.includes(framework)) {
                                    analysis.css_frameworks.push(framework);
                                }
                            });
                        }
                        
                    } catch (e) {
                        // Skip elements that can't be accessed
                        continue;
                    }
                }
                
                // Convert colors to array and limit
                analysis.color_palette = Array.from(colors).slice(0, 30);
                
                // Remove duplicate fonts and limit
                analysis.font_families = [...new Set(analysis.font_families)].slice(0, 15);
                
                // Detect primary layout type
                if (analysis.grid_systems.length > 0) {
                    analysis.layout_type = 'grid';
                } else if (analysis.flexbox_usage > 5) {
                    analysis.layout_type = 'flex';
                } else {
                    analysis.layout_type = 'traditional';
                }
                
                // Extract responsive breakpoints from CSS
                const breakpoints = new Set();
                try {
                    for (let stylesheet of document.styleSheets) {
                        try {
                            for (let rule of stylesheet.cssRules) {
                                if (rule.type === CSSRule.MEDIA_RULE) {
                                    const mediaText = rule.media.mediaText;
                                    const widthMatches = mediaText.match(/\\((?:max-|min-)?width:\\s*(\\d+)px\\)/g);
                                    if (widthMatches) {
                                        widthMatches.forEach(match => {
                                            const width = parseInt(match.match(/\\d+/)[0]);
                                            if (width > 200 && width < 2000) { // Reasonable breakpoint range
                                                breakpoints.add(width);
                                            }
                                        });
                                    }
                                }
                            }
                        } catch (e) {
                            // Can't access cross-origin stylesheets
                            continue;
                        }
                    }
                } catch (e) {
                    // StyleSheets access failed
                }
                
                analysis.responsive_breakpoints = Array.from(breakpoints).sort((a, b) => a - b);
                
                // Analyze spacing patterns
                const spacingValues = new Set();
                for (let element of Array.from(elements).slice(0, 200)) { // Limit to first 200 elements
                    try {
                        const style = window.getComputedStyle(element);
                        ['margin', 'padding'].forEach(prop => {
                            const value = style.getPropertyValue(prop);
                            if (value && value !== '0px' && value !== 'initial') {
                                spacingValues.add(value);
                            }
                        });
                    } catch (e) {
                        continue;
                    }
                }
                
                analysis.spacing_patterns = Array.from(spacingValues).slice(0, 20);
                
                return analysis;
            }
            
            return analyzeEnhancedLayout();
        })()
        """
    
    async def _wait_for_dynamic_content(self, page) -> None:
        """Enhanced waiting strategy for dynamic content."""
        try:
            # Wait for network idle
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Wait for common dynamic content indicators
            await page.evaluate("""
                async () => {
                    // Wait for common framework indicators
                    const frameworks = ['React', 'Vue', 'Angular', '$', 'jQuery'];
                    let frameworkLoaded = false;
                    
                    for (const fw of frameworks) {
                        if (window[fw]) {
                            frameworkLoaded = true;
                            break;
                        }
                    }
                    
                    if (frameworkLoaded) {
                        // Additional wait for framework initialization
                        await new Promise(resolve => setTimeout(resolve, 3000));
                    }
                    
                    // Wait for any remaining animations to complete
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
                    return true;
                }
            """)
            
            # Check for lazy-loaded content
            await page.evaluate("""
                () => {
                    // Scroll to trigger lazy loading
                    window.scrollTo(0, document.body.scrollHeight);
                    window.scrollTo(0, 0);
                }
            """)
            
            # Final wait for lazy content to load
            await page.wait_for_timeout(2000)
        
        except Exception as e:
            logger.warning(f"Enhanced waiting failed, proceeding with extraction: {str(e)}")

    async def extract_dom_structure(
        self,
        url: str,
        session_id: str,
        wait_for_load: bool = True,
        include_computed_styles: bool = True,
        max_depth: int = 10
    ) -> DOMExtractionResult:
        """Enhanced DOM extraction with proper dynamic content waiting."""
        start_time = time.time()
        
        logger.info(f"Starting enhanced DOM extraction for {url}")
        
        if not self.browser_manager:
            raise BrowserError("Browser manager not available")
        
        try:
            async with self.browser_manager.page_context() as page:
                # Navigate to URL
                await self.browser_manager.navigate_to_url(page, url, wait_for="networkidle")
                
                if wait_for_load:
                    # Enhanced waiting strategy for dynamic content
                    await self._wait_for_dynamic_content(page)
                
                # Extract page structure metadata
                page_structure = await self._extract_page_structure(page, url)
                
                # Extract DOM elements with dynamic content support
                logger.info("Extracting DOM elements with dynamic content...")
                dom_data = await page.evaluate(self._javascript_extractors["dom_extractor"])
                
                if not dom_data.get("page_fully_loaded"):
                    logger.warning("Page may not be fully loaded - extraction might be incomplete")
                
                elements = [ExtractedElement(**elem) for elem in dom_data["elements"]]
                
                # Extract stylesheets with enhanced CSS rule extraction
                logger.info("Extracting enhanced stylesheets...")
                style_data = await page.evaluate(self._get_style_extractor_script())
                stylesheets = [ExtractedStylesheet(**sheet) for sheet in style_data["stylesheets"]]
                
                # Extract assets with better URL resolution
                logger.info("Extracting assets with enhanced resolution...")
                asset_data = await page.evaluate(self._javascript_extractors["asset_extractor"])
                assets = []
                for asset_info in asset_data["assets"]:
                    try:
                        asset = ExtractedAsset(
                            url=urljoin(url, asset_info["url"]),
                            asset_type=asset_info["asset_type"],
                            is_background=asset_info.get("is_background", False),
                            usage_context=asset_info.get("usage_context", []),
                            alt_text=asset_info.get("alt_text"),
                            dimensions=tuple(asset_info["dimensions"]) if asset_info.get("dimensions") else None
                        )
                        assets.append(asset)
                    except Exception as e:
                        logger.warning(f"Failed to process asset {asset_info.get('url', 'unknown')}: {str(e)}")
                        continue
                
                # Enhanced layout analysis
                logger.info("Performing enhanced layout analysis...")
                layout_data = await page.evaluate(self._get_layout_analyzer_script())
                
                extraction_time = time.time() - start_time
                
                result = DOMExtractionResult(
                    url=url,
                    session_id=session_id,
                    timestamp=time.time(),
                    extraction_time=extraction_time,
                    page_structure=page_structure,
                    elements=elements,
                    stylesheets=stylesheets,
                    assets=assets,
                    layout_analysis=layout_data,
                    color_palette=layout_data.get("color_palette", []),
                    font_families=layout_data.get("font_families", []),
                    responsive_breakpoints=layout_data.get("responsive_breakpoints", []),
                    dom_depth=dom_data.get("dom_depth", 0),
                    total_elements=len(elements),
                    total_stylesheets=len(stylesheets),
                    total_assets=len(assets),
                    success=True
                )
                
                logger.info(
                    f"Enhanced DOM extraction completed: {len(elements)} elements, "
                    f"{len(stylesheets)} stylesheets, {len(assets)} assets "
                    f"in {extraction_time:.2f}s"
                )
                
                return result
                
        except Exception as e:
            # Error handling remains the same
            extraction_time = time.time() - start_time
            error_msg = f"Enhanced DOM extraction failed: {str(e)}"
            logger.error(error_msg)
            
            return DOMExtractionResult(
                url=url,
                session_id=session_id,
                timestamp=time.time(),
                extraction_time=extraction_time,
                page_structure=PageStructure(),
                elements=[],
                stylesheets=[],
                assets=[],
                layout_analysis={},
                color_palette=[],
                font_families=[],
                responsive_breakpoints=[],
                success=False,
                error_message=error_msg
            )
    
    async def _extract_page_structure(self, page, url: str) -> PageStructure:
        """Extract page metadata and structure information."""
        try:
            # Extract basic page metadata
            structure_script = """
            (() => {
                function extractPageStructure() {
                    const structure = {
                        title: document.title || null,
                        lang: document.documentElement.lang || null,
                        charset: document.characterSet || null,
                        openGraph: {},
                        schemaOrg: []
                    };
                    
                    // Extract meta tags
                    const metaTags = document.querySelectorAll('meta');
                    for (let meta of metaTags) {
                        const name = meta.getAttribute('name') || meta.getAttribute('property');
                        const content = meta.getAttribute('content');
                        
                        if (name && content) {
                            if (name === 'description') {
                                structure.metaDescription = content;
                            } else if (name === 'keywords') {
                                structure.metaKeywords = content;
                            } else if (name === 'viewport') {
                                structure.viewport = content;
                            } else if (name.startsWith('og:')) {
                                structure.openGraph[name] = content;
                            }
                        }
                    }
                    
                    // Extract favicon
                    const favicon = document.querySelector('link[rel*="icon"]');
                    if (favicon && favicon.href) {
                        structure.faviconUrl = favicon.href;
                    }
                    
                    // Extract canonical URL
                    const canonical = document.querySelector('link[rel="canonical"]');
                    if (canonical && canonical.href) {
                        structure.canonicalUrl = canonical.href;
                    }
                    
                    // Extract JSON-LD structured data
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (let script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent);
                            structure.schemaOrg.push(data);
                        } catch (e) {
                            // Invalid JSON, skip
                        }
                    }
                    
                    return structure;
                }
                
                return extractPageStructure();
            })()
            """
            
            structure_data = await page.evaluate(structure_script)
            
            return PageStructure(
                title=structure_data.get("title"),
                meta_description=structure_data.get("metaDescription"),
                meta_keywords=structure_data.get("metaKeywords"),
                lang=structure_data.get("lang"),
                charset=structure_data.get("charset"),
                viewport=structure_data.get("viewport"),
                favicon_url=structure_data.get("faviconUrl"),
                canonical_url=structure_data.get("canonicalUrl"),
                open_graph=structure_data.get("openGraph", {}),
                schema_org=structure_data.get("schemaOrg", [])
            )
            
        except Exception as e:
            logger.warning(f"Error extracting page structure: {str(e)}")
            return PageStructure()
    
    async def save_extraction_result(
        self,
        result: DOMExtractionResult,
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
                data = asdict(result)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                    
            elif output_format == "html":
                # Generate HTML report
                html_content = self._generate_html_report(result)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
            else:
                raise ValueError(f"Unsupported output format: {output_format}")
            
            logger.info(f"Extraction result saved to {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving extraction result: {str(e)}")
            raise ProcessingError(f"Failed to save extraction result: {str(e)}")
    
    def _generate_html_report(self, result: DOMExtractionResult) -> str:
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
                    {self._generate_color_samples(result.color_palette)}
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
                {self._generate_elements_html(result.elements[:50])}
            </div>

            <div class="section">
                <h2>Assets ({len(result.assets)})</h2>
                {self._generate_assets_html(result.assets[:100])}
            </div>

        </body>
        </html>
        """
        return html
    
    def _generate_color_samples(self, colors: List[str]) -> str:
        """Generate HTML for color palette samples."""
        samples = []
        for color in colors[:20]:  # Limit to 20 colors
            # Handle different color formats
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
    
    def _generate_elements_html(self, elements: List[ExtractedElement]) -> str:
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
    
    def _generate_assets_html(self, assets: List[ExtractedAsset]) -> str:
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
    
    async def analyze_page_complexity(self, result: DOMExtractionResult) -> Dict[str, Any]:
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
    
    async def get_extraction_info(self, session_id: str) -> Dict[str, Any]:
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
        self,
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


# Global DOM extraction service instance
dom_extraction_service = DOMExtractionService()