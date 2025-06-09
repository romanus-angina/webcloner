def get_dom_extractor_script() -> str:
    """
    Returns the fixed JavaScript code for enhanced DOM extraction.
    """
    return """
    (() => {
        // Configuration for size limits to prevent token overflow
        const CONFIG = {
            MAX_DEPTH: 6,
            MAX_CHILDREN: 8,
            MAX_CSS_RULES: 3,
            MAX_COMPONENTS: 150,
            MAX_HTML_LENGTH: 500,
            SKIP_SMALL_ELEMENTS: true,
            MIN_ELEMENT_SIZE: 10
        };
        
        let componentCount = 0;
        let extractedAssets = new Set();

        const extractAssetFromElement = (element) => {
            const assets = [];
            
            // Handle IMG tags
            if (element.tagName === 'IMG') {
                const src = element.src || element.getAttribute('src');
                const dataSrc = element.getAttribute('data-src');
                const assetUrl = src || dataSrc;
                
                if (assetUrl && !extractedAssets.has(assetUrl)) {
                    extractedAssets.add(assetUrl);
                    assets.push({
                        url: assetUrl,
                        asset_type: 'image',
                        alt_text: element.alt || element.getAttribute('aria-label') || 'image',
                        width: element.width || element.getAttribute('width'),
                        height: element.height || element.getAttribute('height')
                    });
                }
            }
            
            // Handle SVG tags - capture inline SVGs
            if (element.tagName === 'SVG') {
                const svgContent = element.outerHTML;
                const svgId = element.id || element.getAttribute('class') || 'inline-svg';
                
                if (!extractedAssets.has(svgId)) {
                    extractedAssets.add(svgId);
                    assets.push({
                        content: svgContent,
                        asset_type: 'svg',
                        alt_text: svgId,
                        is_inline: true
                    });
                }
            }
            
            // Handle background images from CSS
            const style = window.getComputedStyle(element);
            const backgroundImage = style.backgroundImage;
            if (backgroundImage && backgroundImage !== 'none') {
                const urlMatch = backgroundImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                if (urlMatch && urlMatch[1] && !extractedAssets.has(urlMatch[1])) {
                    extractedAssets.add(urlMatch[1]);
                    assets.push({
                        url: urlMatch[1],
                        asset_type: 'background-image',
                        alt_text: 'background image',
                        usage_context: 'background'
                    });
                }
            }
            
            // Handle picture elements
            if (element.tagName === 'PICTURE') {
                const img = element.querySelector('img');
                if (img && img.src && !extractedAssets.has(img.src)) {
                    extractedAssets.add(img.src);
                    assets.push({
                        url: img.src,
                        asset_type: 'image',
                        alt_text: img.alt || 'picture',
                        is_responsive: true
                    });
                }
            }
            
            return assets;
        };

        const getAppliedCssRules = (element) => {
            if (componentCount > CONFIG.MAX_COMPONENTS) return [];
            
            const sheets = Array.from(document.styleSheets);
            const rules = [];
            let ruleCount = 0;
            
            for (const sheet of sheets) {
                try {
                    if (!sheet.cssRules || ruleCount >= CONFIG.MAX_CSS_RULES) break;
                    
                    for (const rule of sheet.cssRules) {
                        if (ruleCount >= CONFIG.MAX_CSS_RULES) break;
                        
                        try {
                            if (element.matches(rule.selectorText.split(':')[0])) {
                                const essentialProps = extractEssentialCSS(rule.style);
                                if (essentialProps) {
                                    rules.push({
                                        selector: rule.selectorText,
                                        css_text: essentialProps
                                    });
                                    ruleCount++;
                                }
                            }
                        } catch(e) { 
                            // Ignore invalid selectors
                        }
                    }
                } catch (e) { 
                    // Ignore cross-origin errors
                }
            }
            return rules;
        };

        const extractEssentialCSS = (style) => {
            const importantProps = [
                'display', 'position', 'flex', 'grid', 'width', 'height', 
                'margin', 'padding', 'background', 'background-image', 'background-color',
                'color', 'font-family', 'font-size', 'font-weight', 'text-align', 
                'border', 'border-radius', 'opacity', 'transform'
            ];
            
            const essential = [];
            for (const prop of importantProps) {
                const value = style.getPropertyValue(prop);
                if (value && value !== 'initial' && value !== 'normal' && value !== 'none') {
                    essential.push(prop + ': ' + value);
                }
            }
            
            return essential.length > 0 ? essential.join('; ') : null;
        };

        const shouldSkipElement = (element) => {
            if (CONFIG.SKIP_SMALL_ELEMENTS) {
                const rect = element.getBoundingClientRect();
                if (rect.width < CONFIG.MIN_ELEMENT_SIZE || rect.height < CONFIG.MIN_ELEMENT_SIZE) {
                    return true;
                }
            }
            
            const style = window.getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                return true;
            }
            
            return false;
        };

        const getComponentType = (element) => {
            const tag = element.tagName.toLowerCase();
            const classList = Array.from(element.classList);

            // Prioritize visual elements
            if (tag === 'img' || tag === 'picture') return 'image';
            if (tag === 'svg') return 'svg';
            if (tag === 'header' || classList.some(c => c.includes('header'))) return 'header';
            if (tag === 'nav' || classList.some(c => c.includes('nav'))) return 'navbar';
            if (tag === 'main' || classList.some(c => c.includes('main'))) return 'section';
            if (tag === 'button' || element.getAttribute('role') === 'button') return 'button';
            if (tag === 'a') return 'link';
            if (tag === 'form') return 'form';
            if (tag === 'input' || tag === 'textarea' || tag === 'select') return 'input';
            if (classList.some(c => c.includes('card'))) return 'card';
            if (['section', 'article', 'aside'].includes(tag)) return 'section';
            
            return 'div';
        };

        const buildComponentTree = (element, depth, allAssets) => {
            depth = depth || 0;
            allAssets = allAssets || [];
            
            if (depth >= CONFIG.MAX_DEPTH || componentCount >= CONFIG.MAX_COMPONENTS) {
                return null;
            }
            
            const tagName = element.tagName.toLowerCase();
            
            if (['script', 'style', 'meta', 'link', 'head', 'title', 'noscript'].includes(tagName)) {
                return null;
            }
            
            if (shouldSkipElement(element)) {
                return null;
            }

            componentCount++;

            const componentType = getComponentType(element);
            
            // Extract assets from this element
            const elementAssets = extractAssetFromElement(element);
            allAssets.push(...elementAssets);
            
            // Create HTML snippet - preserve more for assets
            let htmlSnippet = element.outerHTML;
            if (htmlSnippet.length > CONFIG.MAX_HTML_LENGTH) {
                if (['img', 'svg', 'picture'].includes(tagName)) {
                    // For assets, keep more of the HTML
                    htmlSnippet = htmlSnippet.substring(0, CONFIG.MAX_HTML_LENGTH * 2);
                } else {
                    const match = htmlSnippet.match(/^<[^>]+>/);
                    htmlSnippet = match ? match[0] : '<' + tagName + '>';
                }
            }

            const componentData = {
                component_type: componentType,
                html_snippet: htmlSnippet,
                relevant_css_rules: getAppliedCssRules(element),
                children: []
            };

            // Enhanced asset handling
            if (componentType === 'image') {
                if (element.src) {
                    componentData.asset_url = element.src;
                }
                componentData.html_snippet = element.outerHTML;
                if (element.alt) {
                    componentData.label = element.alt;
                }
            } else if (componentType === 'svg') {
                componentData.html_snippet = element.outerHTML;
                componentData.asset_url = 'inline-svg';
                componentData.label = element.getAttribute('aria-label') || 'svg-icon';
            } else if (['link', 'button'].includes(componentType)) {
                const text = element.textContent && element.textContent.trim();
                if (text && text.length > 0 && text.length < 100) {
                    componentData.label = text;
                }
            }

            // Process children
            const children = Array.from(element.children);
            const maxChildren = Math.min(children.length, CONFIG.MAX_CHILDREN);
            
            for (let i = 0; i < maxChildren; i++) {
                if (componentCount >= CONFIG.MAX_COMPONENTS) break;
                
                const childComponent = buildComponentTree(children[i], depth + 1, allAssets);
                if (childComponent) {
                    componentData.children.push(childComponent);
                }
            }
            
            return componentData;
        };

        // Start extraction
        const allAssets = [];
        const blueprint = buildComponentTree(document.body, 0, allAssets);
        
        console.log('Component extraction completed: ' + componentCount + ' components, ' + allAssets.length + ' assets');
        
        return { 
            blueprint: blueprint,
            assets: allAssets,
            metadata: {
                total_components: componentCount,
                total_assets: allAssets.length,
                extraction_limited: componentCount >= CONFIG.MAX_COMPONENTS
            }
        };
    })();
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
