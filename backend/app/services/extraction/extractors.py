# backend/app/services/extraction/extractors.py

def get_dom_extractor_script() -> str:
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

def get_asset_extractor_script() -> str:
    """JavaScript for asset discovery."""
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
                    asset_type: type,
                    usage_context: context,
                    is_background: false
                };
                
                if (element) {
                    if (element.alt) asset.alt_text = element.alt;
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
                                asset_type: 'image',
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

def get_style_extractor_script() -> str:
    """Comprehensive CSS and style extraction."""
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

def get_layout_analyzer_script() -> str:
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