import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from ..utils.logger import get_logger

logger = get_logger(__name__)

class HTMLRewriterService:
    """
    Enhanced service to rewrite asset paths and handle inline assets.
    """

    def rewrite_asset_paths(self, html_content: str, asset_map: Dict[str, str]) -> str:
        """
        Enhanced asset path rewriting with better asset handling.
        """
        if not asset_map:
            logger.info("No assets to rewrite, returning original HTML.")
            return html_content

        logger.info(f"Rewriting {len(asset_map)} asset paths in generated HTML.")
        
        # Handle both BeautifulSoup parsing and regex replacement
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Enhanced asset rewriting
            self._rewrite_img_tags(soup, asset_map)
            self._rewrite_svg_tags(soup, asset_map)
            self._rewrite_background_images(soup, asset_map)
            self._rewrite_style_blocks(soup, asset_map)
            self._handle_inline_assets(soup, asset_map)
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"Failed to parse HTML with BeautifulSoup: {e}")
            # Fallback to regex-based replacement
            return self._regex_asset_replacement(html_content, asset_map)

    def _rewrite_img_tags(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Rewrite src attributes in img tags."""
        img_tags = soup.find_all('img', src=True)
        for img in img_tags:
            original_src = img.get('src')
            if original_src in asset_map:
                new_src = asset_map[original_src]
                logger.debug(f"Rewriting img src: {original_src} -> {new_src}")
                img['src'] = new_src
            
            # Also check data-src for lazy loading
            data_src = img.get('data-src')
            if data_src and data_src in asset_map:
                img['data-src'] = asset_map[data_src]

    def _rewrite_svg_tags(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Handle SVG tags and xlink:href attributes."""
        # Handle SVG use elements
        use_tags = soup.find_all('use')
        for use in use_tags:
            href = use.get('href') or use.get('xlink:href')
            if href and href in asset_map:
                new_href = asset_map[href]
                logger.debug(f"Rewriting SVG use href: {href} -> {new_href}")
                if use.get('href'):
                    use['href'] = new_href
                if use.get('xlink:href'):
                    use['xlink:href'] = new_href

    def _rewrite_background_images(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Rewrite background images in style attributes."""
        elements_with_style = soup.find_all(style=True)
        for element in elements_with_style:
            style_str = element['style']
            new_style = self._replace_urls_in_css(style_str, asset_map)
            if new_style != style_str:
                element['style'] = new_style

    def _rewrite_style_blocks(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Rewrite URLs in style blocks."""
        style_blocks = soup.find_all('style')
        for block in style_blocks:
            if block.string:
                new_css = self._replace_urls_in_css(block.string, asset_map)
                if new_css != block.string:
                    block.string = new_css

    def _handle_inline_assets(self, soup: BeautifulSoup, asset_map: Dict[str, str]) -> None:
        """Handle inline assets like SVGs stored in asset_map."""
        for original_key, new_value in asset_map.items():
            if original_key.startswith('inline-svg-') and new_value.startswith('/static/'):
                # Try to find placeholder text and replace with actual SVG
                placeholder_patterns = [
                    original_key,
                    original_key.replace('inline-svg-', ''),
                    'svg-icon',
                    'inline-svg'
                ]
                
                for pattern in placeholder_patterns:
                    # Look for text nodes that might be placeholders
                    text_nodes = soup.find_all(text=re.compile(pattern, re.IGNORECASE))
                    for text_node in text_nodes:
                        parent = text_node.parent
                        if parent and parent.name in ['div', 'span', 'i']:
                            # Replace with img tag pointing to the SVG
                            img_tag = soup.new_tag('img', src=new_value, alt='icon')
                            parent.replace_with(img_tag)

    def _replace_urls_in_css(self, css_text: str, asset_map: Dict[str, str]) -> str:
        """Replace URL references in CSS text."""
        def replace_url(match):
            url = match.group(1).strip('\'"')
            if url in asset_map:
                new_url = asset_map[url]
                logger.debug(f"Rewriting CSS url(): {url} -> {new_url}")
                return f"url('{new_url}')"
            return match.group(0)
        
        # Pattern to match url() in CSS
        url_pattern = r'url\s*\(\s*([^)]+)\s*\)'
        return re.sub(url_pattern, replace_url, css_text)

    def _regex_asset_replacement(self, html_content: str, asset_map: Dict[str, str]) -> str:
        """Fallback regex-based asset replacement."""
        logger.info("Using fallback regex-based asset replacement")
        
        modified_html = html_content
        
        for original_url, new_path in asset_map.items():
            # Replace in src attributes
            modified_html = re.sub(
                rf'src=["\']({re.escape(original_url)})["\']',
                f'src="{new_path}"',
                modified_html
            )
            
            # Replace in CSS url() functions
            modified_html = re.sub(
                rf'url\(["\']?{re.escape(original_url)}["\']?\)',
                f'url("{new_path}")',
                modified_html
            )
            
            # Replace in data-src attributes
            modified_html = re.sub(
                rf'data-src=["\']({re.escape(original_url)})["\']',
                f'data-src="{new_path}"',
                modified_html
            )
        
        return modified_html

    def inject_missing_assets(self, html_content: str, missing_assets: List[Dict[str, Any]]) -> str:
        """
        Inject missing assets that should have been included but weren't.
        """
        if not missing_assets:
            return html_content
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find a good place to inject assets (preferably in header or main content)
            injection_point = soup.find('header') or soup.find('main') or soup.find('body')
            
            if not injection_point:
                return html_content
            
            for asset in missing_assets:
                if asset.get('asset_type') == 'image' and asset.get('local_path'):
                    # Create img tag
                    img_tag = soup.new_tag(
                        'img', 
                        src=asset['local_path'],
                        alt=asset.get('alt_text', 'Missing asset'),
                        style="max-width: 100px; height: auto; margin: 5px;"
                    )
                    injection_point.insert(0, img_tag)
                    logger.info(f"Injected missing image: {asset['local_path']}")
                    
                elif asset.get('asset_type') == 'svg' and asset.get('content'):
                    # Create SVG element
                    svg_soup = BeautifulSoup(asset['content'], 'html.parser')
                    svg_tag = svg_soup.find('svg')
                    if svg_tag:
                        injection_point.insert(0, svg_tag)
                        logger.info("Injected missing SVG")
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"Failed to inject missing assets: {e}")
            return html_content

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