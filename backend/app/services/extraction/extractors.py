def get_dom_extractor_script() -> str:
    """
    Returns the JavaScript code for advanced DOM, style, and asset extraction.
    This version returns component types in lowercase to match the Python Enum.
    """
    return """
    (() => {
        const getAppliedCssRules = (element) => {
            const sheets = Array.from(document.styleSheets);
            const rules = [];
            for (const sheet of sheets) {
                try {
                    if (!sheet.cssRules) continue;
                    for (const rule of sheet.cssRules) {
                        // Check for both simple and pseudo-class selectors
                        if (element.matches(rule.selectorText.split(':')[0])) {
                            rules.push({
                                selector: rule.selectorText,
                                css_text: rule.style.cssText
                            });
                        }
                    }
                } catch (e) { /* Ignore cross-origin errors */ }
            }
            return rules;
        };

        const getComponentType = (element) => {
            const tag = element.tagName.toLowerCase();
            const classList = Array.from(element.classList);

            // Return lowercase strings to match Python Enum
            if (tag === 'header' || classList.some(c => c.includes('header'))) return 'header';
            if (tag === 'nav' || classList.some(c => c.includes('nav'))) return 'navbar';
            if (tag === 'img') return 'image';
            if (tag === 'svg') return 'svg';
            if (tag === 'button' || element.getAttribute('role') === 'button') return 'button';
            if (tag === 'a') return 'link';
            if (tag === 'form') return 'form';
            if (tag === 'input' || tag === 'textarea' || tag === 'select') return 'input';
            if (classList.some(c => c.includes('card'))) return 'card';
            if (['main', 'section', 'article'].includes(tag)) return 'section';
            return 'div';
        };

        const buildComponentTree = (element) => {
            const tagName = element.tagName.toLowerCase();
            if (['script', 'style', 'meta', 'link', 'head', 'title'].includes(tagName)) {
                return null;
            }

            const componentData = {
                component_type: getComponentType(element),
                html_snippet: element.outerHTML.split('>')[0] + '>',
                relevant_css_rules: getAppliedCssRules(element),
                children: []
            };

            if (['image', 'svg'].includes(componentData.component_type)) {
                componentData.html_snippet = element.outerHTML;
                if (element.src) {
                    componentData.asset_url = new URL(element.src, document.baseURI).href;
                }
            } else if (['link', 'button'].includes(componentData.component_type)) {
                componentData.label = element.textContent.trim();
            }

            for (const child of element.children) {
                const childComponent = buildComponentTree(child);
                if (childComponent) {
                    componentData.children.push(childComponent);
                }
            }
            return componentData;
        };

        const blueprint = buildComponentTree(document.body);
        return { blueprint };
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
