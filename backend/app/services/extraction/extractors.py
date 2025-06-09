def get_dom_extractor_script() -> str:
    """Enhanced DOM extraction script with a robust XPath generator."""
    return """
    (() => {
        function getXPath(element) {
            // If the element is null or not an element node, stop.
            if (!element || element.nodeType !== 1) {
                return '';
            }
            // If the element has a unique ID, use that for a direct path.
            if (element.id) {
                return `//*[@id='${element.id}']`;
            }
            // The base case: stop at the body tag.
            if (element === document.body) {
                return '/html/body';
            }
            // Fallback for elements without a parent (like the html element).
            if (!element.parentNode) {
                return element.tagName.toLowerCase();
            }

            let ix = 0;
            const siblings = element.parentNode.childNodes;
            for (let i = 0; i < siblings.length; i++) {
                const sibling = siblings[i];
                if (sibling === element) {
                    // Recursively get the path of the parent and append the current element's tag and index.
                    return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                }
                // Count only element siblings of the same tag.
                if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                    ix++;
                }
            }
        }

        const elements = [];
        document.querySelectorAll('*').forEach(element => {
             const tagName = element.tagName.toLowerCase();
             if (tagName === 'script' || tagName === 'style') return;
             elements.push({
                tag_name: tagName,
                element_id: element.id || null,
                class_names: element.className && typeof element.className.split === 'function' ? element.className.split(' ').filter(c => c) : [],
                text_content: element.firstChild?.textContent?.trim() || null,
                children_count: element.children.length,
                xpath: getXPath(element)
             });
        });
        return { elements, total_elements: elements.length, dom_depth: 0 };
    })()
    """

def get_asset_extractor_script() -> str:
    """JavaScript for asset discovery."""
    return """
    (() => {
        const assets = [];
        const processedUrls = new Set();
        function addAsset(url, asset_type, element = null, context = []) {
            if (!url || processedUrls.has(url)) return;
            try {
                const fullUrl = new URL(url, document.baseURI).href;
                processedUrls.add(fullUrl);
                const asset = { url: fullUrl, asset_type, usage_context: context };
                if (element && element.alt) asset.alt_text = element.alt;
                assets.push(asset);
            } catch (e) { console.warn(`Invalid asset URL: ${url}`); }
        }
        document.querySelectorAll('img[src]').forEach(img => addAsset(img.src, 'image', img, ['img-tag']));
        document.querySelectorAll('*').forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.backgroundImage && style.backgroundImage !== 'none') {
                const urlMatch = style.backgroundImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                if (urlMatch) addAsset(urlMatch[1], 'image', null, ['background-image']);
            }
        });
        return { assets };
    })()
    """

def get_style_extractor_script() -> str:
    """Consolidated JavaScript to extract a full 'Design System' from the page."""
    return """
    (() => {
        const getStyle = (el, prop) => window.getComputedStyle(el).getPropertyValue(prop);

        // 1. Theme and Color Palette Analysis
        const bodyStyle = window.getComputedStyle(document.body);
        const primary_background = bodyStyle.backgroundColor;
        const primary_text = bodyStyle.color;
        let is_dark_theme = false;
        if (primary_background.startsWith('rgb')) {
            const rgb = primary_background.match(/\\d+/g).map(Number);
            const brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000;
            is_dark_theme = brightness < 128;
        }
        const allColors = new Set([primary_background, primary_text]);
        document.querySelectorAll('*').forEach(el => {
            const style = window.getComputedStyle(el);
            allColors.add(style.color);
            allColors.add(style.backgroundColor);
            allColors.add(style.borderColor);
        });
        
        const themeData = {
            primary_background,
            primary_text,
            is_dark_theme,
            all_colors: Array.from(allColors).filter(c => c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent')
        };

        // 2. Typography Analysis
        const typographyData = { body: {}, h1: {}, h2: {}, h3: {}, all_families: new Set() };
        const getTypographyStyle = (el) => ({
            font_family: getStyle(el, 'font-family'),
            font_size: getStyle(el, 'font-size'),
            font_weight: getStyle(el, 'font-weight'),
            line_height: getStyle(el, 'line-height'),
            color: getStyle(el, 'color')
        });
        typographyData.body = getTypographyStyle(document.body);
        typographyData.all_families.add(typographyData.body.font_family);

        ['h1', 'h2', 'h3'].forEach(tag => {
            const el = document.querySelector(tag);
            if (el) {
                typographyData[tag] = getTypographyStyle(el);
                typographyData.all_families.add(typographyData[tag].font_family);
            }
        });
        typographyData.all_families = Array.from(typographyData.all_families).flatMap(f => f.split(',')).map(f => f.trim().replace(/['"]/g, ''));

        // 3. CSS Variables
        const cssVariablesData = {};
        const rootStyles = window.getComputedStyle(document.documentElement);
        for (let i = 0; i < rootStyles.length; i++) {
            const prop = rootStyles[i];
            if (prop.startsWith('--')) {
                cssVariablesData[prop] = rootStyles.getPropertyValue(prop).trim();
            }
        }
        
        // 4. Responsive Breakpoints
        const breakpoints = new Set();
        if (document.styleSheets) {
            Array.from(document.styleSheets).forEach(sheet => {
                try {
                    if (sheet.cssRules) {
                        Array.from(sheet.cssRules).forEach(rule => {
                            if (rule.type === CSSRule.MEDIA_RULE && rule.media.mediaText.includes('width')) {
                                const match = rule.media.mediaText.match(/(\\d+)px/);
                                if (match) breakpoints.add(parseInt(match[1]));
                            }
                        });
                    }
                } catch(e) {}
            });
        }
        
        return {
            theme: themeData,
            typography: typographyData,
            css_variables: cssVariablesData,
            responsive_breakpoints: Array.from(breakpoints).sort((a,b) => a - b),
            layout_type: 'grid'
        };
    })()
    """
