def get_dom_extractor_script() -> str:
    """
    Returns the enhanced JavaScript code for DOM extraction with better asset detection.
    """
    return """
    (() => {
        // Enhanced configuration for better asset detection
        const CONFIG = {
            MAX_DEPTH: 6,
            MAX_CHILDREN: 8,
            MAX_CSS_RULES: 3,
            MAX_COMPONENTS: 150,
            MAX_HTML_LENGTH: 500,
            SKIP_SMALL_ELEMENTS: true,
            MIN_ELEMENT_SIZE: 10,
            ASSET_TIMEOUT: 5000,
            MAX_ASSETS: 100
        };
        
        let componentCount = 0;
        let extractedAssets = new Map(); // Use Map for better deduplication
        let assetId = 0;

        // ENHANCED: Extract ALL images including IMG tags
        const extractAllImages = () => {
            const images = [];
            
            // Get all IMG tags
            const imgTags = document.querySelectorAll('img');
            console.log(`Found ${imgTags.length} img tags`);
            
            imgTags.forEach((img, index) => {
                const sources = [
                    img.src,
                    img.getAttribute('src'),
                    img.getAttribute('data-src'),
                    img.getAttribute('data-lazy-src'),
                    img.getAttribute('data-original'),
                    img.dataset?.src
                ].filter(Boolean);
                
                sources.forEach(src => {
                    if (src && !extractedAssets.has(src)) {
                        extractedAssets.set(src, ++assetId);
                        
                        images.push({
                            id: assetId,
                            url: src,
                            asset_type: 'image',
                            alt_text: img.alt || img.getAttribute('aria-label') || `image-${index}`,
                            width: img.naturalWidth || img.width,
                            height: img.naturalHeight || img.height,
                            classes: Array.from(img.classList),
                            usage_context: ['img-tag'],
                            element_location: `IMG[${index}]`
                        });
                    }
                });
            });
            
            console.log(`Extracted ${images.length} images from IMG tags`);
            return images;
        };

        // ENHANCED: Extract ALL SVGs
        const extractAllSVGs = () => {
            const svgs = [];
            const svgTags = document.querySelectorAll('svg');
            
            console.log(`Found ${svgTags.length} SVG elements`);
            
            svgTags.forEach((svg, index) => {
                const svgContent = svg.outerHTML;
                const svgId = svg.id || svg.getAttribute('class') || `svg-${index}`;
                
                if (!extractedAssets.has(svgId)) {
                    extractedAssets.set(svgId, ++assetId);
                    
                    svgs.push({
                        id: assetId,
                        content: svgContent,
                        asset_type: 'svg',
                        alt_text: svg.getAttribute('aria-label') || svg.title || svgId,
                        is_inline: true,
                        viewBox: svg.getAttribute('viewBox'),
                        width: svg.getAttribute('width'),
                        height: svg.getAttribute('height'),
                        classes: Array.from(svg.classList),
                        usage_context: ['inline-svg'],
                        element_location: `SVG[${index}]`
                    });
                }
            });
            
            console.log(`Extracted ${svgs.length} SVG elements`);
            return svgs;
        };

        // ENHANCED: Extract background images from ALL elements
        const extractBackgroundImages = () => {
            const backgrounds = [];
            const elements = document.querySelectorAll('*');
            
            console.log(`Scanning ${elements.length} elements for background images`);
            
            elements.forEach((el, index) => {
                const style = window.getComputedStyle(el);
                const bgImage = style.backgroundImage;
                
                if (bgImage && bgImage !== 'none' && bgImage.includes('url(')) {
                    const urlMatch = bgImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                    if (urlMatch && urlMatch[1] && !extractedAssets.has(urlMatch[1])) {
                        const url = urlMatch[1];
                        extractedAssets.set(url, ++assetId);
                        
                        backgrounds.push({
                            id: assetId,
                            url: url,
                            asset_type: 'background-image',
                            alt_text: el.getAttribute('aria-label') || el.title || 'background-image',
                            element_tag: el.tagName,
                            classes: Array.from(el.classList),
                            usage_context: ['background-css'],
                            element_location: `${el.tagName}[${index}]`
                        });
                    }
                }
            });
            
            console.log(`Extracted ${backgrounds.length} background images`);
            return backgrounds;
        };

        // ENHANCED: Extract assets from stylesheets
        const extractAssetsFromStylesheets = () => {
            const assets = [];
            
            try {
                const sheets = Array.from(document.styleSheets);
                console.log(`Scanning ${sheets.length} stylesheets`);
                
                for (const sheet of sheets) {
                    try {
                        const rules = sheet.cssRules || sheet.rules;
                        if (!rules) continue;
                        
                        for (const rule of rules) {
                            if (rule.style) {
                                // Check background-image
                                const bgImage = rule.style.backgroundImage;
                                if (bgImage && bgImage !== 'none') {
                                    const urlMatch = bgImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                                    if (urlMatch && urlMatch[1] && !extractedAssets.has(urlMatch[1])) {
                                        extractedAssets.set(urlMatch[1], ++assetId);
                                        assets.push({
                                            id: assetId,
                                            url: urlMatch[1],
                                            asset_type: 'css-background',
                                            alt_text: 'css-background',
                                            css_selector: rule.selectorText,
                                            usage_context: ['stylesheet']
                                        });
                                    }
                                }
                            }
                        }
                    } catch (e) {
                        // Cross-origin or other stylesheet error
                        continue;
                    }
                }
            } catch (error) {
                console.warn('Stylesheet asset extraction error:', error);
            }
            
            console.log(`Extracted ${assets.length} assets from stylesheets`);
            return assets;
        };

        // Component detection functions (simplified for now)
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

        // START ENHANCED EXTRACTION
        console.log('Starting enhanced asset extraction...');
        const allAssets = [];
        
        // 1. Extract ALL images first (most important)
        const allImages = extractAllImages();
        allAssets.push(...allImages);
        
        // 2. Extract ALL SVGs
        const allSVGs = extractAllSVGs();
        allAssets.push(...allSVGs);
        
        // 3. Extract background images
        const backgroundImages = extractBackgroundImages();
        allAssets.push(...backgroundImages);
        
        // 4. Extract from stylesheets
        const stylesheetAssets = extractAssetsFromStylesheets();
        allAssets.push(...stylesheetAssets);
        
        console.log(`Total assets found: IMG=${allImages.length}, SVG=${allSVGs.length}, BG=${backgroundImages.length}, CSS=${stylesheetAssets.length}`);
        
        // Build component tree
        const blueprint = buildComponentTree(document.body, 0, allAssets);
        console.log('DOM extraction completed. Total assets found:', allAssets.length);
        
        // Deduplicate assets
        const uniqueAssets = [];
        const seenUrls = new Set();
        
        for (const asset of allAssets) {
            const key = asset.url || asset.content?.substring(0, 100) || asset.id;
            if (!seenUrls.has(key)) {
                seenUrls.add(key);
                uniqueAssets.push(asset);
            }
        }
        
        console.log('Enhanced component extraction completed:', {
            components: componentCount,
            total_assets: allAssets.length,
            unique_assets: uniqueAssets.length,
            assetTypes: [...new Set(uniqueAssets.map(a => a.asset_type))]
        });
        
        // Return results
        return { 
            blueprint: blueprint,
            assets: uniqueAssets.slice(0, CONFIG.MAX_ASSETS),
            metadata: {
                total_components: componentCount,
                total_assets: uniqueAssets.length,
                extraction_limited: componentCount >= CONFIG.MAX_COMPONENTS,
                asset_types: [...new Set(uniqueAssets.map(a => a.asset_type))],
                has_react: !!document.querySelector('[data-reactroot]'),
                has_vue: !!window.Vue,
                has_angular: !!window.ng,
                debug_all_assets_count: allAssets.length,
                debug_unique_assets_count: uniqueAssets.length,
                debug_seen_urls_count: seenUrls.size,
                debug_asset_breakdown: {
                    images: allImages.length,
                    svgs: allSVGs.length,
                    backgrounds: backgroundImages.length,
                    css_assets: stylesheetAssets.length
                }
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
