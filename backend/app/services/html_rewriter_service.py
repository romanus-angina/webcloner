import re
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup, Tag, NavigableString
import json

from ..utils.logger import get_logger

logger = get_logger(__name__)

class HTMLRewriterService:
    """
    Enhanced HTML rewriter that handles modern web patterns including:
    - React/Vue style dynamic content
    - CSS custom properties
    - Data URLs and blob URLs
    - Background images and mask images
    - Responsive image handling
    """

    def __init__(self):
        self.rewrite_stats = {
            'img_tags_processed': 0,
            'background_images_processed': 0,
            'svg_elements_processed': 0,
            'data_urls_processed': 0,
            'css_rules_processed': 0,
            'react_patterns_processed': 0
        }

    def rewrite_asset_paths(self, html_content: str, asset_map: Dict[str, str]) -> str:
        """
        Enhanced asset path rewriting with support for modern web patterns.
        """
        if not asset_map:
            logger.info("No assets to rewrite, returning original HTML.")
            return html_content

        logger.info(f"Rewriting {len(asset_map)} asset paths in generated HTML.")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Enhanced asset rewriting
            self._rewrite_img_tags(soup, asset_map)
            self._rewrite_picture_elements(soup, asset_map)
            self._rewrite_svg_tags(soup, asset_map)
            self._rewrite_background_images(soup, asset_map)
            self._rewrite_style_blocks(soup, asset_map)
            self._rewrite_css_custom_properties(soup, asset_map)
            self._handle_inline_assets(soup, asset_map)
            self._handle_data_urls(soup, asset_map)
            self._handle_react_patterns(soup, asset_map)
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"Failed to parse HTML with BeautifulSoup: {e}")
            # Fallback to regex-based replacement
            return self._regex_asset_replacement(html_content, asset_map)

    def _rewrite_img_tags(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Enhanced img tag rewriting with lazy loading and responsive handling."""
        img_tags = soup.find_all('img')
        
        for img in img_tags:
            # Handle multiple src attributes
            src_attributes = ['src', 'data-src', 'data-lazy-src', 'data-original']
            
            for attr in src_attributes:
                original_src = img.get(attr)
                if original_src and original_src in asset_map:
                    new_src = asset_map[original_src]
                    logger.debug(f"Rewriting img {attr}: {original_src} -> {new_src}")
                    img[attr] = new_src
                    self.rewrite_stats['img_tags_processed'] += 1
            
            # Handle srcset attributes
            srcset = img.get('srcset')
            if srcset:
                new_srcset = self._rewrite_srcset(srcset, asset_map)
                if new_srcset != srcset:
                    img['srcset'] = new_srcset
                    logger.debug(f"Rewriting img srcset")

    def _rewrite_picture_elements(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Rewrite picture elements and their source children."""
        picture_tags = soup.find_all('picture')
        
        for picture in picture_tags:
            # Handle source elements
            sources = picture.find_all('source')
            for source in sources:
                srcset = source.get('srcset')
                if srcset:
                    new_srcset = self._rewrite_srcset(srcset, asset_map)
                    if new_srcset != srcset:
                        source['srcset'] = new_srcset
            
            # Handle img element within picture
            img = picture.find('img')
            if img:
                self._rewrite_img_tags(BeautifulSoup(str(img), 'html.parser'), asset_map)

    def _rewrite_srcset(self, srcset: str, asset_map: Dict[str, str]) -> str:
        """Rewrite srcset attribute values."""
        srcset_parts = []
        
        for part in srcset.split(','):
            part = part.strip()
            if ' ' in part:
                url, descriptor = part.rsplit(' ', 1)
                url = url.strip()
                if url in asset_map:
                    url = asset_map[url]
                srcset_parts.append(f"{url} {descriptor}")
            else:
                url = part.strip()
                if url in asset_map:
                    url = asset_map[url]
                srcset_parts.append(url)
        
        return ', '.join(srcset_parts)

    def _rewrite_svg_tags(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Enhanced SVG handling including use elements and symbol references."""
        # Handle SVG use elements
        use_tags = soup.find_all('use')
        for use in use_tags:
            for attr in ['href', 'xlink:href']:
                href = use.get(attr)
                if href and href in asset_map:
                    new_href = asset_map[href]
                    logger.debug(f"Rewriting SVG use {attr}: {href} -> {new_href}")
                    use[attr] = new_href
                    self.rewrite_stats['svg_elements_processed'] += 1
        
        # Handle SVG image elements
        svg_images = soup.find_all('image')  # SVG image elements
        for img in svg_images:
            for attr in ['href', 'xlink:href']:
                href = img.get(attr)
                if href and href in asset_map:
                    new_href = asset_map[href]
                    logger.debug(f"Rewriting SVG image {attr}: {href} -> {new_href}")
                    img[attr] = new_href
                    self.rewrite_stats['svg_elements_processed'] += 1

    def _rewrite_background_images(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Enhanced background image rewriting."""
        elements_with_style = soup.find_all(style=True)
        
        for element in elements_with_style:
            style_str = element['style']
            new_style = self._replace_urls_in_css(style_str, asset_map)
            if new_style != style_str:
                element['style'] = new_style
                self.rewrite_stats['background_images_processed'] += 1

    def _rewrite_style_blocks(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Enhanced style block rewriting."""
        style_blocks = soup.find_all('style')
        
        for block in style_blocks:
            if block.string:
                original_css = block.string
                new_css = self._replace_urls_in_css(original_css, asset_map)
                if new_css != original_css:
                    block.string = new_css
                    self.rewrite_stats['css_rules_processed'] += 1

    def _rewrite_css_custom_properties(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Handle CSS custom properties (CSS variables) that might contain URLs."""
        style_blocks = soup.find_all('style')
        
        for block in style_blocks:
            if block.string:
                css_content = block.string
                
                # Find CSS custom properties with URLs
                custom_prop_pattern = r'(--[\w-]+)\s*:\s*url\(["\']?([^"\')\s]+)["\']?\)'
                
                def replace_custom_prop(match):
                    prop_name = match.group(1)
                    url = match.group(2)
                    
                    if url in asset_map:
                        new_url = asset_map[url]
                        logger.debug(f"Rewriting CSS custom property {prop_name}: {url} -> {new_url}")
                        return f'{prop_name}: url("{new_url}")'
                    
                    return match.group(0)
                
                new_css = re.sub(custom_prop_pattern, replace_custom_prop, css_content)
                if new_css != css_content:
                    block.string = new_css

    def _handle_inline_assets(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Handle inline assets and placeholder replacements."""
        # Look for asset placeholders in text content
        for text_node in soup.find_all(text=True):
            if isinstance(text_node, NavigableString):
                parent = text_node.parent
                
                # Skip script and style tags
                if parent and parent.name in ['script', 'style']:
                    continue
                
                # Look for asset references in text
                text_content = str(text_node)
                
                # Check for inline SVG references
                for original_key, new_value in asset_map.items():
                    if original_key.startswith('inline-svg-') and text_content.strip() in [
                        original_key, 
                        original_key.replace('inline-svg-', ''),
                        'svg-icon',
                        'icon'
                    ]:
                        # Replace text node with SVG or img tag
                        if new_value.startswith('/static/'):
                            new_tag = soup.new_tag('img', src=new_value, alt='icon', **{'class': 'inline-icon'})
                        elif new_value.startswith('data:image/svg'):
                            new_tag = soup.new_tag('img', src=new_value, alt='icon', **{'class': 'inline-icon'})
                        else:
                            # Try to use SVG content directly
                            try:
                                svg_soup = BeautifulSoup(new_value, 'html.parser')
                                svg_tag = svg_soup.find('svg')
                                if svg_tag:
                                    new_tag = svg_tag
                                else:
                                    continue
                            except:
                                continue
                        
                        text_node.replace_with(new_tag)
                        break

    def _handle_data_urls(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Handle data URL replacements."""
        for data_key, local_path in asset_map.items():
            if data_key.startswith('data:'):
                # Find elements using this data URL
                for attr in ['src', 'href', 'data-src']:
                    elements = soup.find_all(attrs={attr: data_key})
                    for element in elements:
                        element[attr] = local_path
                        self.rewrite_stats['data_urls_processed'] += 1
                        logger.debug(f"Replaced data URL with local path")

    def _handle_react_patterns(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Handle React/Vue style patterns and component props."""
        # Look for elements with React-style props
        for element in soup.find_all():
            # Check for data attributes that might contain image URLs
            for attr_name, attr_value in element.attrs.items():
                if attr_name.startswith('data-') and isinstance(attr_value, str):
                    # Check if it's a URL pattern
                    if any(ext in attr_value.lower() for ext in ['.jpg', '.png', '.svg', '.gif', '.webp']):
                        if attr_value in asset_map:
                            element[attr_name] = asset_map[attr_value]
                            self.rewrite_stats['react_patterns_processed'] += 1
                            logger.debug(f"Replaced React data attribute: {attr_name}")

    def _replace_urls_in_css(self, css_text: str, asset_map: Dict[str, str]) -> str:
        """Enhanced URL replacement in CSS with support for multiple backgrounds."""
        def replace_url(match):
            url = match.group(1).strip('\'"')
            if url in asset_map:
                new_url = asset_map[url]
                logger.debug(f"Rewriting CSS url(): {url} -> {new_url}")
                return f"url('{new_url}')"
            return match.group(0)
        
        # Enhanced pattern to match url() in CSS, including data URLs
        url_pattern = r'url\s*\(\s*([^)]+)\s*\)'
        return re.sub(url_pattern, replace_url, css_text)

    def _regex_asset_replacement(self, html_content: str, asset_map: Dict[str, str]) -> str:
        """Enhanced fallback regex-based asset replacement."""
        logger.info("Using enhanced fallback regex-based asset replacement")
        
        modified_html = html_content
        
        for original_url, new_path in asset_map.items():
            # Escape special regex characters in URL
            escaped_url = re.escape(original_url)
            
            # Replace in various contexts
            replacements = [
                # Standard src attributes
                (rf'src=["\']({escaped_url})["\']', f'src="{new_path}"'),
                # Data attributes
                (rf'data-src=["\']({escaped_url})["\']', f'data-src="{new_path}"'),
                (rf'data-lazy-src=["\']({escaped_url})["\']', f'data-lazy-src="{new_path}"'),
                # CSS url() functions
                (rf'url\(["\']?{escaped_url}["\']?\)', f'url("{new_path}")'),
                # Srcset attributes
                (rf'{escaped_url}(\s+[\d.]+[wx])', f'{new_path}\\1'),
                # SVG href attributes
                (rf'href=["\']({escaped_url})["\']', f'href="{new_path}"'),
                (rf'xlink:href=["\']({escaped_url})["\']', f'xlink:href="{new_path}"'),
            ]
            
            for pattern, replacement in replacements:
                modified_html = re.sub(pattern, replacement, modified_html, flags=re.IGNORECASE)
        
        return modified_html

    def inject_missing_assets(self, html_content: str, missing_assets: List[Dict[str, Any]]) -> str:
        """Enhanced missing asset injection with better placement logic."""
        if not missing_assets:
            return html_content
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find strategic locations for asset placement
            header = soup.find('header')
            nav = soup.find('nav') 
            main = soup.find('main') or soup.find('body')
            
            for asset in missing_assets:
                if not asset.get('success'):
                    continue
                    
                asset_type = asset.get('asset_type', '')
                local_path = asset.get('local_path', '')
                alt_text = asset.get('alt_text', '').lower()
                
                if not local_path:
                    continue
                
                # Logo placement
                if any(keyword in alt_text for keyword in ['logo', 'brand']):
                    target = header or nav or main
                    if target and not target.find('img', alt=re.compile(r'logo|brand', re.I)):
                        logo_element = self._create_asset_element(soup, asset, 'logo')
                        if logo_element:
                            target.insert(0, logo_element)
                            logger.info(f"Integrated missing logo: {alt_text}")
                
                # SVG icons
                elif asset_type == 'svg':
                    # Look for elements that might need icons
                    potential_targets = soup.find_all(['button', 'a', 'span'], 
                                                    class_=re.compile(r'icon|btn|link', re.I))
                    
                    for target in potential_targets[:3]:
                        if not target.find(['img', 'svg']):
                            icon_element = self._create_asset_element(soup, asset, 'icon')
                            if icon_element:
                                target.insert(0, icon_element)
                                logger.info(f"Integrated missing SVG icon: {alt_text}")
                                break
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"Failed to inject missing assets: {e}")
            return html_content

    def _create_asset_element(self, soup: BeautifulSoup, asset: Dict[str, Any], element_type: str) -> Optional[Tag]:
        """Create appropriate HTML element for an asset."""
        try:
            local_path = asset.get('local_path')
            if not local_path:
                return None
            
            asset_type = asset.get('asset_type', '')
            alt_text = asset.get('alt_text', element_type)
            
            if asset_type == 'svg' and asset.get('content'):
                # Use inline SVG content
                try:
                    svg_soup = BeautifulSoup(asset['content'], 'html.parser')
                    svg_tag = svg_soup.find('svg')
                    if svg_tag:
                        # Add classes for styling
                        existing_classes = svg_tag.get('class', [])
                        if isinstance(existing_classes, str):
                            existing_classes = existing_classes.split()
                        svg_tag['class'] = existing_classes + [f'injected-{element_type}']
                        return svg_tag
                except:
                    pass
            
            # Create img tag
            img_attrs = {
                'src': local_path,
                'alt': alt_text,
                'class': f'injected-{element_type}'
            }
            
            # Add appropriate sizing based on element type
            if element_type == 'logo':
                img_attrs.update({'style': 'height: 40px; width: auto; max-width: 200px;'})
            elif element_type == 'icon':
                img_attrs.update({'style': 'width: 1.5em; height: 1.5em; display: inline-block;'})
            
            return soup.new_tag('img', **img_attrs)
            
        except Exception as e:
            logger.warning(f"Failed to create asset element: {e}")
            return None

    def enhance_asset_integration(self, html_content: str, all_assets: List[Dict[str, Any]]) -> str:
        """
        Enhanced method to ensure all assets are properly integrated.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check for missing critical assets
            missing_logos = []
            missing_icons = []
            
            for asset in all_assets:
                asset_path = asset.get('local_path', '')
                alt_text = asset.get('alt_text', '').lower()
                
                # Check if this asset is mentioned in HTML
                if asset_path and not (asset_path in html_content or asset.get('original_url', '') in html_content):
                    if 'logo' in alt_text or 'brand' in alt_text:
                        missing_logos.append(asset)
                    elif 'icon' in alt_text or asset.get('asset_type') == 'svg':
                        missing_icons.append(asset)
            
            # Inject missing logos in header
            if missing_logos:
                header = soup.find('header') or soup.find('nav')
                if header:
                    for logo in missing_logos[:1]:  # Only inject first logo
                        if logo.get('local_path'):
                            logo_img = soup.new_tag(
                                'img', 
                                src=logo['local_path'],
                                alt=logo.get('alt_text', 'Logo'),
                                style="height: 40px; width: auto;"
                            )
                            header.insert(0, logo_img)
                            logger.info("Injected missing logo in header")
            
            # Inject critical SVG icons
            if missing_icons:
                # Look for potential icon containers
                icon_containers = soup.find_all(['i', 'span', 'div'], class_=re.compile(r'icon|svg', re.I))
                
                for i, container in enumerate(icon_containers[:len(missing_icons)]):
                    if i < len(missing_icons):
                        icon = missing_icons[i]
                        if icon.get('content'):
                            # Replace with actual SVG
                            svg_soup = BeautifulSoup(icon['content'], 'html.parser')
                            svg_tag = svg_soup.find('svg')
                            if svg_tag:
                                # Add proper sizing
                                svg_tag['style'] = "width: 1em; height: 1em; display: inline-block;"
                                container.clear()
                                container.append(svg_tag)
                                logger.info("Replaced icon container with SVG")
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"Failed to enhance asset integration: {e}")
            return html_content

    def get_rewrite_stats(self) -> Dict[str, int]:
        """Get statistics about the rewriting process."""
        return self.rewrite_stats.copy()