#!/usr/bin/env python3
"""
Enhanced Highlander Racing Website Cloner
Improved error handling and fallback strategies for failed downloads.
"""

import os
import re
import sys
import time
import json
import urllib.parse
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

class EnhancedWebsiteCloner:
    def __init__(self, base_url, output_dir="highlander_racing_clone"):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.output_dir = Path(output_dir)
        self.downloaded_files = set()
        self.failed_downloads = []
        self.skipped_downloads = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # URLs to skip (known problematic patterns)
        self.skip_patterns = [
            r'https://lirp\.cdn-website\.com/$',  # Empty CDN URLs
            r'https://lirp\.cdn-website\.com$',   # Root CDN URLs
            r'.*#.*',  # Fragment URLs (fonts with anchors)
            r'https://discord\.com/widget\?.*',  # Discord widgets
        ]
        
        # Font fallbacks
        self.font_fallbacks = {
            'dm-font': 'Arial, sans-serif',
            'dm-social-font': 'Arial, sans-serif',
        }
        
        # Sitemap URLs
        self.sitemap_urls = [
            "https://www.highlanderracing.org/powertrain-23e",
            "https://www.highlanderracing.org",
            "https://www.highlanderracing.org/work",
            "https://www.highlanderracing.org/sponsors",
            "https://www.highlanderracing.org/suspension04e214a3",
            "https://www.highlanderracing.org/media",
            "https://www.highlanderracing.org/accumulatord0614381",
            "https://www.highlanderracing.org/drivetrain673c018e",
            "https://www.highlanderracing.org/contact_us",
            "https://www.highlanderracing.org/cars",
            "https://www.highlanderracing.org/steering8d92569a",
            "https://www.highlanderracing.org/hr15-c",
            "https://www.highlanderracing.org/chassiscd1c83a9",
            "https://www.highlanderracing.org/hr09-c",
            "https://www.highlanderracing.org/aerodynamicsde6ccd7f",
            "https://www.highlanderracing.org/hr19-e",
            "https://www.highlanderracing.org/hr18-e",
            "https://www.highlanderracing.org/corners",
            "https://www.highlanderracing.org/hr23-e",
            "https://www.highlanderracing.org/our-team",
            "https://www.highlanderracing.org/resources",
            "https://www.highlanderracing.org/controlsda4b082a",
            "https://www.highlanderracing.org/corners-23e",
            "https://www.highlanderracing.org/aerodynamics-23e",
            "https://www.highlanderracing.org/accumulator-23e",
            "https://www.highlanderracing.org/steering-23e",
            "https://www.highlanderracing.org/chassis-23e",
            "https://www.highlanderracing.org/controls-23e",
            "https://www.highlanderracing.org/suspension-23e",
            "https://www.highlanderracing.org/autonomous_karting_fsae",
            "https://www.highlanderracing.org/hr24-e",
            "https://www.highlanderracing.org/powertrain-25e",
            "https://www.highlanderracing.org/suspension-25e",
            "https://www.highlanderracing.org/accumulator-25e",
            "https://www.highlanderracing.org/aerodynamics-25e",
            "https://www.highlanderracing.org/chassis-25e",
            "https://www.highlanderracing.org/copy-of-controls-23e"
        ]

    def should_skip_url(self, url):
        """Check if URL should be skipped based on patterns"""
        for pattern in self.skip_patterns:
            if re.match(pattern, url):
                return True
        return False

    def create_font_fallback_css(self):
        """Create a fallback CSS file for missing fonts"""
        fallback_css = """
/* Fallback fonts for missing Duda fonts */
@font-face {
    font-family: 'dm-font';
    src: local('Arial'), local('Helvetica'), local('sans-serif');
    font-weight: normal;
    font-style: normal;
}

@font-face {
    font-family: 'dm-social-font';
    src: local('Arial'), local('Helvetica'), local('sans-serif');
    font-weight: normal;
    font-style: normal;
}

/* Override any font references */
body, html {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.dm-font, [class*="dm-font"] {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
}

.dm-social-font, [class*="dm-social-font"] {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
}
"""
        fallback_path = self.output_dir / 'assets' / 'css' / 'font-fallbacks.css'
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(fallback_path, 'w') as f:
            f.write(fallback_css)
        
        print(f"✓ Created font fallback CSS: {fallback_path}")
        return fallback_path

    def sanitize_filename(self, filename):
        """Sanitize filename for filesystem compatibility"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.replace(' ', '_')
        return filename

    def url_to_filepath(self, url):
        """Convert URL to local file path"""
        parsed = urlparse(url)
        path = parsed.path.lstrip('/')
        
        if not path or path.endswith('/'):
            path += 'index.html'
        elif not Path(path).suffix:
            path += '.html'
            
        # Handle query parameters in filename
        if parsed.query:
            # Remove common parameters that don't affect content
            query_params = parsed.query
            # Remove cache-busting parameters
            query_params = re.sub(r'[?&]v=\d+', '', query_params)
            query_params = re.sub(r'[?&]mxo7pn', '', query_params)
            if query_params:
                base_path = Path(path)
                path = f"{base_path.stem}_{query_params[:10]}{base_path.suffix}"
        
        # Sanitize the path
        parts = path.split('/')
        sanitized_parts = [self.sanitize_filename(part) for part in parts]
        
        return self.output_dir / '/'.join(sanitized_parts)

    def download_file_with_retry(self, url, local_path=None, max_retries=3):
        """Download a single file with retry logic and better error handling"""
        if url in self.downloaded_files:
            return local_path
        
        # Check if we should skip this URL
        if self.should_skip_url(url):
            self.skipped_downloads.append((url, "Skipped - matches skip pattern"))
            return None
        
        for attempt in range(max_retries):
            try:
                print(f"Downloading: {url} (attempt {attempt + 1})")
                
                # Use different strategies based on URL type
                if 'font' in url.lower():
                    # For fonts, try with different headers
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/font-woff2,application/font-woff,font/woff2,font/woff,*/*',
                        'Referer': self.base_url
                    }
                    response = self.session.get(url, timeout=30, headers=headers)
                else:
                    response = self.session.get(url, timeout=30)
                
                response.raise_for_status()
                
                if local_path is None:
                    local_path = self.url_to_filepath(url)
                
                # Create directory if it doesn't exist
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write content based on type
                if 'text' in response.headers.get('content-type', '').lower():
                    with open(local_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                else:
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                
                self.downloaded_files.add(url)
                print(f"✓ Saved: {local_path}")
                return local_path
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    error_msg = str(e)
                    print(f"✗ Failed to download {url}: {error_msg}")
                    self.failed_downloads.append((url, error_msg))
                    
                    # Try to create placeholder for critical files
                    if 'font' in url.lower():
                        self.create_font_placeholder(url, local_path)
                    
                    return None
                else:
                    print(f"  Retrying in {2 ** attempt} seconds...")
                    time.sleep(2 ** attempt)
            
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Unexpected error downloading {url}: {error_msg}")
                self.failed_downloads.append((url, error_msg))
                return None

    def create_font_placeholder(self, font_url, local_path):
        """Create a placeholder font file or CSS rule"""
        if local_path:
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                # Create an empty SVG font file
                placeholder_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <text x="50" y="50" text-anchor="middle" font-family="Arial">Font</text>
</svg>'''
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(placeholder_content)
                print(f"✓ Created font placeholder: {local_path}")
            except Exception as e:
                print(f"✗ Could not create font placeholder: {e}")

    def extract_assets_from_html(self, html_content, base_url):
        """Extract all asset URLs from HTML content with better filtering"""
        soup = BeautifulSoup(html_content, 'html.parser')
        assets = set()
        
        # Extract different types of assets
        asset_selectors = [
            ('link', 'href'),
            ('script', 'src'),
            ('img', 'src'),
            ('img', 'data-src'),
            ('source', 'src'),
            ('source', 'srcset'),
            ('video', 'src'),
            ('audio', 'src'),
            ('embed', 'src'),
            ('object', 'data'),
            ('iframe', 'src'),
        ]
        
        for tag, attr in asset_selectors:
            elements = soup.find_all(tag, {attr: True})
            for element in elements:
                asset_url = element.get(attr)
                if asset_url:
                    # Handle srcset (multiple URLs)
                    if attr == 'srcset':
                        urls = re.findall(r'([^\s,]+)', asset_url)
                        for url in urls:
                            if url and not url.endswith('w') and not url.endswith('x'):
                                full_url = urljoin(base_url, url)
                                if not self.should_skip_url(full_url):
                                    assets.add(full_url)
                    else:
                        full_url = urljoin(base_url, asset_url)
                        if not self.should_skip_url(full_url):
                            assets.add(full_url)
        
        # Extract CSS @import and url() references
        css_links = soup.find_all('link', rel='stylesheet')
        for link in css_links:
            href = link.get('href')
            if href:
                css_url = urljoin(base_url, href)
                if not self.should_skip_url(css_url):
                    assets.add(css_url)
        
        return assets

    def extract_assets_from_css(self, css_content, base_url):
        """Extract asset URLs from CSS content with better filtering"""
        assets = set()
        
        # Find all url() references in CSS
        url_pattern = r'url\([\'"]?([^\'"\)]+)[\'"]?\)'
        matches = re.findall(url_pattern, css_content)
        
        for match in matches:
            # Skip data URLs and problematic URLs
            if match.startswith('data:') or self.should_skip_url(match):
                continue
            full_url = urljoin(base_url, match)
            if not self.should_skip_url(full_url):
                assets.add(full_url)
        
        return assets

    def update_html_with_fallbacks(self, html_content, base_url):
        """Update HTML links and add fallback CSS for missing fonts"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Add fallback CSS link to head
        head = soup.find('head')
        if head:
            fallback_link = soup.new_tag('link', rel='stylesheet', href='assets/css/font-fallbacks.css')
            head.insert(0, fallback_link)
        
        # Update asset links
        link_updates = [
            ('link', 'href'),
            ('script', 'src'),
            ('img', 'src'),
            ('img', 'data-src'),
            ('a', 'href'),
            ('source', 'src'),
            ('video', 'src'),
            ('audio', 'src'),
            ('embed', 'src'),
            ('object', 'data'),
            ('iframe', 'src'),
        ]
        
        for tag, attr in link_updates:
            elements = soup.find_all(tag, {attr: True})
            for element in elements:
                original_url = element.get(attr)
                if original_url and not self.should_skip_url(original_url):
                    # Convert to relative paths for internal links
                    if original_url.startswith(self.base_url) or (
                        not original_url.startswith('http') and 
                        not original_url.startswith('mailto:') and 
                        not original_url.startswith('tel:') and 
                        not original_url.startswith('#')
                    ):
                        full_url = urljoin(base_url, original_url) if not original_url.startswith('http') else original_url
                        if self.domain in full_url:
                            relative_path = self.get_relative_path(full_url, base_url)
                            element[attr] = relative_path
        
        return str(soup)

    def get_relative_path(self, target_url, current_url):
        """Get relative path from current URL to target URL"""
        target_parsed = urlparse(target_url)
        current_parsed = urlparse(current_url)
        
        target_path = target_parsed.path.lstrip('/')
        current_path = current_parsed.path.lstrip('/')
        
        # Handle index pages
        if not target_path or target_path.endswith('/'):
            target_path += 'index.html'
        elif not Path(target_path).suffix:
            target_path += '.html'
            
        if not current_path or current_path.endswith('/'):
            current_path += 'index.html'
        elif not Path(current_path).suffix:
            current_path += '.html'
        
        # Sanitize paths
        target_parts = target_path.split('/')
        current_parts = current_path.split('/')
        
        target_sanitized = '/'.join([self.sanitize_filename(part) for part in target_parts])
        current_sanitized = '/'.join([self.sanitize_filename(part) for part in current_parts])
        
        try:
            target_full = Path(target_sanitized)
            current_full = Path(current_sanitized)
            current_dir = current_full.parent
            
            relative_path = os.path.relpath(target_full, current_dir)
            return relative_path.replace('\\', '/')
        except ValueError:
            return target_sanitized

    def clone_page(self, url):
        """Clone a single page and its assets with enhanced error handling"""
        print(f"\n📄 Cloning page: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Save original HTML
            local_path = self.url_to_filepath(url)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Extract assets from HTML
            assets = self.extract_assets_from_html(response.text, url)
            print(f"Found {len(assets)} assets")
            
            # Download assets with better error handling
            successful_downloads = 0
            for asset_url in assets:
                if asset_url.startswith('http'):
                    asset_path = self.url_to_filepath(asset_url)
                    result = self.download_file_with_retry(asset_url, asset_path)
                    if result:
                        successful_downloads += 1
                        
                        # If it's a CSS file, extract its assets too
                        if asset_url.endswith('.css'):
                            try:
                                css_response = self.session.get(asset_url, timeout=30)
                                css_response.raise_for_status()
                                css_assets = self.extract_assets_from_css(css_response.text, asset_url)
                                for css_asset in css_assets:
                                    if css_asset.startswith('http'):
                                        css_asset_path = self.url_to_filepath(css_asset)
                                        css_result = self.download_file_with_retry(css_asset, css_asset_path)
                                        if css_result:
                                            successful_downloads += 1
                            except Exception as e:
                                print(f"Warning: Could not process CSS assets from {asset_url}: {e}")
            
            # Update HTML with fallbacks and save
            updated_html = self.update_html_with_fallbacks(response.text, url)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(updated_html)
            
            print(f"✓ Page saved: {local_path}")
            print(f"✓ Assets downloaded: {successful_downloads}/{len(assets)}")
            return local_path
            
        except Exception as e:
            print(f"✗ Failed to clone page {url}: {e}")
            self.failed_downloads.append((url, str(e)))
            return None

    def clone_website(self):
        """Clone the entire website with enhanced error handling"""
        print(f"🚀 Starting enhanced website clone of {self.base_url}")
        print(f"📁 Output directory: {self.output_dir.absolute()}")
        
        # Create font fallback CSS first
        self.create_font_fallback_css()
        
        # Clone all pages from sitemap
        print(f"\n📋 Cloning {len(self.sitemap_urls)} pages from sitemap...")
        
        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=3) as executor:  # Reduced workers to be more gentle
            future_to_url = {executor.submit(self.clone_page, url): url for url in self.sitemap_urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"✗ Error processing {url}: {e}")
        
        # Generate enhanced summary
        self.generate_enhanced_summary()
        
        # Create deployment configs
        self.create_deployment_configs()
        
        # Create local server script
        self.create_local_server_script()
        
        print(f"\n🎉 Enhanced website cloning complete!")
        print(f"📁 Files saved to: {self.output_dir.absolute()}")
        print(f"✅ Successfully downloaded: {len(self.downloaded_files)} files")
        print(f"⏭️  Skipped downloads: {len(self.skipped_downloads)}")
        print(f"❌ Failed downloads: {len(self.failed_downloads)}")
        
        # Show improvement
        total_attempts = len(self.downloaded_files) + len(self.skipped_downloads) + len(self.failed_downloads)
        success_rate = (len(self.downloaded_files) / total_attempts) * 100 if total_attempts > 0 else 0
        print(f"📊 Success rate: {success_rate:.1f}%")
        
        print(f"\n🚀 Ready for deployment to:")
        print(f"   • Vercel: vercel --prod")
        print(f"   • Netlify: netlify deploy --prod --dir .")
        print(f"   • GitHub Pages: Push to gh-pages branch")
        print(f"💡 To run locally: python local_server.py")

    def generate_enhanced_summary(self):
        """Generate an enhanced summary with detailed failure analysis"""
        # Categorize failures
        failure_categories = {
            'fonts': [],
            'empty_urls': [],
            'background_images': [],
            'redirects': [],
            'other': []
        }
        
        for url, error in self.failed_downloads:
            if 'font' in url.lower():
                failure_categories['fonts'].append((url, error))
            elif url.endswith('/') or 'cdn-website.com/' == url:
                failure_categories['empty_urls'].append((url, error))
            elif 'background' in url.lower():
                failure_categories['background_images'].append((url, error))
            elif 'redirect' in error.lower():
                failure_categories['redirects'].append((url, error))
            else:
                failure_categories['other'].append((url, error))
        
        summary = {
            'base_url': self.base_url,
            'total_pages': len(self.sitemap_urls),
            'downloaded_files': len(self.downloaded_files),
            'skipped_downloads': len(self.skipped_downloads),
            'failed_downloads': len(self.failed_downloads),
            'failure_categories': {k: len(v) for k, v in failure_categories.items()},
            'failure_details': failure_categories,
            'skipped_details': self.skipped_downloads,
            'improvements': {
                'font_fallbacks_created': True,
                'enhanced_error_handling': True,
                'retry_logic': True,
                'skip_patterns': len(self.skip_patterns)
            }
        }
        
        with open(self.output_dir / 'enhanced_clone_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📊 Enhanced Clone Summary:")
        print(f"   Pages in sitemap: {summary['total_pages']}")
        print(f"   Files downloaded: {summary['downloaded_files']}")
        print(f"   Files skipped: {summary['skipped_downloads']}")
        print(f"   Failed downloads: {summary['failed_downloads']}")
        print(f"\n🔍 Failure breakdown:")
        for category, count in summary['failure_categories'].items():
            print(f"   • {category.replace('_', ' ').title()}: {count}")

    def create_deployment_configs(self):
        """Create deployment configuration files"""
        # Vercel config
        vercel_config = {
            "version": 2,
            "name": "highlander-racing",
            "builds": [{"src": "*.html", "use": "@vercel/static"}],
            "routes": [{"src": "/(.*)", "dest": "/$1"}],
            "headers": [
                {
                    "source": "/(.*)",
                    "headers": [{"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}]
                }
            ]
        }
        
        with open(self.output_dir / 'vercel.json', 'w') as f:
            json.dump(vercel_config, f, indent=2)
        
        # Netlify config
        netlify_config = """[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
  force = false

[[headers]]
  for = "/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000"
    
[[headers]]
  for = "*.html"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"
"""
        
        with open(self.output_dir / 'netlify.toml', 'w') as f:
            f.write(netlify_config)
        
        # GitHub Pages config
        with open(self.output_dir / '.nojekyll', 'w') as f:
            f.write('# Bypass Jekyll processing\n')

    def create_local_server_script(self):
        """Create a local server script"""
        server_script = '''#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
import os

PORT = 8000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print(f"🌐 Serving website at http://localhost:{PORT}")
        webbrowser.open(f'http://localhost:{PORT}')
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\\n👋 Server stopped")
'''
        
        with open(self.output_dir / 'local_server.py', 'w') as f:
            f.write(server_script)
        
        os.chmod(self.output_dir / 'local_server.py', 0o755)

def main():
    """Main function"""
    base_url = "https://www.highlanderracing.org"
    
    print("🏁 Enhanced Highlander Racing Website Cloner")
    print("=" * 50)
    print("🔧 Enhanced Features:")
    print("   • Smart skip patterns for problematic URLs")
    print("   • Font fallback CSS generation")
    print("   • Retry logic with exponential backoff")
    print("   • Better error categorization")
    print("   • Reduced concurrent requests")
    print("=" * 50)
    
    # Allow custom output directory
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "highlander_racing_enhanced"
    
    cloner = EnhancedWebsiteCloner(base_url, output_dir)
    cloner.clone_website()

if __name__ == "__main__":
    main()
    