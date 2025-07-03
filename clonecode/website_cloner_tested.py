#!/usr/bin/env python3
"""
Highlander Racing Website Cloner
Recursively downloads all pages, assets, CSS, and images from your website.
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

class WebsiteCloner:
    def __init__(self, base_url, output_dir="highlander_racing_clone"):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.output_dir = Path(output_dir)
        self.downloaded_files = set()
        self.failed_downloads = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Sitemap URLs from your provided sitemap
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

    def sanitize_filename(self, filename):
        """Sanitize filename for filesystem compatibility"""
        # Remove or replace invalid characters
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
            
        # Sanitize the path
        parts = path.split('/')
        sanitized_parts = [self.sanitize_filename(part) for part in parts]
        
        return self.output_dir / '/'.join(sanitized_parts)

    def download_file(self, url, local_path=None):
        """Download a single file"""
        if url in self.downloaded_files:
            return local_path
            
        try:
            print(f"Downloading: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            if local_path is None:
                local_path = self.url_to_filepath(url)
            
            # Create directory if it doesn't exist
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            if 'text' in response.headers.get('content-type', '').lower():
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
            else:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
            
            self.downloaded_files.add(url)
            print(f"✓ Saved: {local_path}")
            return local_path
            
        except Exception as e:
            print(f"✗ Failed to download {url}: {e}")
            self.failed_downloads.append((url, str(e)))
            return None

    def extract_assets_from_html(self, html_content, base_url):
        """Extract all asset URLs from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        assets = set()
        
        # Extract different types of assets
        asset_selectors = [
            ('link', 'href'),  # CSS, favicons
            ('script', 'src'),  # JavaScript
            ('img', 'src'),     # Images
            ('img', 'data-src'), # Lazy loaded images
            ('source', 'src'),  # Video sources
            ('source', 'srcset'), # Responsive images
            ('video', 'src'),   # Videos
            ('audio', 'src'),   # Audio
            ('embed', 'src'),   # Embedded content
            ('object', 'data'), # Objects
            ('iframe', 'src'),  # Iframes
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
                                assets.add(full_url)
                    else:
                        full_url = urljoin(base_url, asset_url)
                        assets.add(full_url)
        
        # Extract CSS @import and url() references
        css_links = soup.find_all('link', rel='stylesheet')
        for link in css_links:
            href = link.get('href')
            if href:
                css_url = urljoin(base_url, href)
                assets.add(css_url)
        
        # Extract inline CSS url() references
        style_tags = soup.find_all('style')
        for style in style_tags:
            if style.string:
                css_urls = re.findall(r'url\([\'"]?([^\'"\)]+)[\'"]?\)', style.string)
                for url in css_urls:
                    full_url = urljoin(base_url, url)
                    assets.add(full_url)
        
        return assets

    def extract_assets_from_css(self, css_content, base_url):
        """Extract asset URLs from CSS content"""
        assets = set()
        
        # Find all url() references in CSS
        url_pattern = r'url\([\'"]?([^\'"\)]+)[\'"]?\)'
        matches = re.findall(url_pattern, css_content)
        
        for match in matches:
            # Skip data URLs
            if match.startswith('data:'):
                continue
            full_url = urljoin(base_url, match)
            assets.add(full_url)
        
        # Find @import statements
        import_pattern = r'@import\s+[\'"]([^\'"]+)[\'"]'
        imports = re.findall(import_pattern, css_content)
        
        for import_url in imports:
            full_url = urljoin(base_url, import_url)
            assets.add(full_url)
        
        return assets

    def update_html_links(self, html_content, base_url):
        """Update HTML links to point to local files"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Update different types of links
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
                if original_url:
                    # Handle different URL types
                    if original_url.startswith('data:') or original_url.startswith('javascript:'):
                        # Skip data URLs and javascript
                        continue
                    elif original_url.startswith('mailto:') or original_url.startswith('tel:'):
                        # Keep contact links as-is
                        continue
                    elif original_url.startswith('#'):
                        # Keep anchor links as-is
                        continue
                    elif original_url.startswith('http') and self.domain not in original_url:
                        # External link - keep as absolute URL
                        continue
                    else:
                        # Internal link - convert to relative
                        full_url = urljoin(base_url, original_url) if not original_url.startswith('http') else original_url
                        
                        if self.domain in full_url:
                            # This is an internal link
                            if tag == 'a':
                                # For navigation links, use relative paths
                                relative_path = self.get_relative_path(full_url, base_url)
                                element[attr] = relative_path
                            else:
                                # For assets, use relative paths
                                relative_path = self.get_relative_path(full_url, base_url)
                                element[attr] = relative_path
        
        return str(soup)

    def get_relative_path(self, target_url, current_url):
        """Get relative path from current URL to target URL"""
        # Parse URLs to get paths
        target_parsed = urlparse(target_url)
        current_parsed = urlparse(current_url)
        
        # Convert to local file paths
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
        
        # Get relative path
        try:
            target_full = Path(target_sanitized)
            current_full = Path(current_sanitized)
            
            # Get relative path from current file's directory to target
            if current_full.name == 'index.html':
                current_dir = current_full.parent
            else:
                current_dir = current_full.parent
            
            relative_path = os.path.relpath(target_full, current_dir)
            return relative_path.replace('\\', '/')
        except ValueError:
            # Can't create relative path, return target path
            return target_sanitized

    def clone_page(self, url):
        """Clone a single page and its assets"""
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
            
            # Download assets
            for asset_url in assets:
                if asset_url.startswith('http'):
                    asset_path = self.url_to_filepath(asset_url)
                    self.download_file(asset_url, asset_path)
                    
                    # If it's a CSS file, extract its assets too
                    if asset_url.endswith('.css'):
                        try:
                            css_response = self.session.get(asset_url, timeout=30)
                            css_response.raise_for_status()
                            css_assets = self.extract_assets_from_css(css_response.text, asset_url)
                            for css_asset in css_assets:
                                if css_asset.startswith('http'):
                                    css_asset_path = self.url_to_filepath(css_asset)
                                    self.download_file(css_asset, css_asset_path)
                        except Exception as e:
                            print(f"Warning: Could not process CSS assets from {asset_url}: {e}")
            
            # Update HTML links and save
            updated_html = self.update_html_links(response.text, url)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(updated_html)
            
            print(f"✓ Page saved: {local_path}")
            return local_path
            
        except Exception as e:
            print(f"✗ Failed to clone page {url}: {e}")
            self.failed_downloads.append((url, str(e)))
            return None

    def clone_website(self):
        """Clone the entire website"""
        print(f"🚀 Starting website clone of {self.base_url}")
        print(f"📁 Output directory: {self.output_dir.absolute()}")
        
        # Clone all pages from sitemap
        print(f"\n📋 Cloning {len(self.sitemap_urls)} pages from sitemap...")
        
        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(self.clone_page, url): url for url in self.sitemap_urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"✗ Error processing {url}: {e}")
        
        # Generate summary
        self.generate_summary()
        
        # Create deployment configuration files
        self.create_deployment_configs()
        
        print(f"\n🎉 Website cloning complete!")
        print(f"📁 Files saved to: {self.output_dir.absolute()}")
        print(f"✅ Successfully downloaded: {len(self.downloaded_files)} files")
        if self.failed_downloads:
            print(f"❌ Failed downloads: {len(self.failed_downloads)}")
        print(f"\n🚀 Ready for deployment to:")
        print(f"   • Vercel: vercel --prod")
        print(f"   • Netlify: netlify deploy --prod --dir .")
        print(f"   • GitHub Pages: Push to gh-pages branch")
        print(f"💡 To run locally: python local_server.py")

    def generate_summary(self):
        """Generate a summary of the cloning process"""
        summary = {
            'base_url': self.base_url,
            'total_pages': len(self.sitemap_urls),
            'downloaded_files': len(self.downloaded_files),
            'failed_downloads': len(self.failed_downloads),
            'failed_urls': self.failed_downloads
        }
        
        with open(self.output_dir / 'clone_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📊 Clone Summary:")
        print(f"   Pages in sitemap: {summary['total_pages']}")
        print(f"   Files downloaded: {summary['downloaded_files']}")
        print(f"   Failed downloads: {summary['failed_downloads']}")

    def create_deployment_configs(self):
        """Create deployment configuration files for various platforms"""
        
        # Vercel configuration
        vercel_config = {
            "version": 2,
            "name": "highlander-racing",
            "builds": [
                {
                    "src": "*.html",
                    "use": "@vercel/static"
                }
            ],
            "routes": [
                {
                    "src": "/(.*)",
                    "dest": "/$1"
                }
            ],
            "headers": [
                {
                    "source": "/(.*)",
                    "headers": [
                        {
                            "key": "Cache-Control",
                            "value": "public, max-age=31536000, immutable"
                        }
                    ]
                }
            ]
        }
        
        with open(self.output_dir / 'vercel.json', 'w') as f:
            json.dump(vercel_config, f, indent=2)
        
        # Netlify configuration
        netlify_config = """# Netlify configuration
[[redirects]]
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
        
        # GitHub Pages configuration (Jekyll bypass)
        with open(self.output_dir / '.nojekyll', 'w') as f:
            f.write('# Bypass Jekyll processing\n')
        
        # Create a README for deployment
        readme_content = """# Highlander Racing Website

This is a complete clone of the Highlander Racing website, ready for deployment.

## Deploy to Vercel
1. Install Vercel CLI: `npm install -g vercel`
2. Run: `vercel --prod`
3. Follow the prompts

## Deploy to Netlify
1. Install Netlify CLI: `npm install -g netlify-cli`
2. Run: `netlify deploy --prod --dir .`
3. Follow the prompts

## Deploy to GitHub Pages
1. Create a new repository on GitHub
2. Push these files to the `main` branch
3. Enable GitHub Pages in repository settings
4. Set source to `main` branch

## Local Development
Run: `python local_server.py`
Then open: http://localhost:8000

## File Structure
- All HTML pages are at the root level
- Assets are organized in subdirectories
- All links are relative and work on any domain
"""
        
        with open(self.output_dir / 'README.md', 'w') as f:
            f.write(readme_content)
        
        # Create .gitignore
        gitignore_content = """# Local server
local_server.py
*.pyc
__pycache__/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Logs
*.log
clone_summary.json
"""
        
        with open(self.output_dir / '.gitignore', 'w') as f:
            f.write(gitignore_content)

    def create_local_server_script(self):
        """Create a simple local server script"""
        server_script = '''#!/usr/bin/env python3
"""
Simple local server for your cloned website
"""
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
        print(f"📁 Serving from: {os.getcwd()}")
        print("🔧 Press Ctrl+C to stop the server")
        
        # Open browser
        webbrowser.open(f'http://localhost:{PORT}')
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\\n👋 Server stopped")
'''
        
        with open(self.output_dir / 'local_server.py', 'w') as f:
            f.write(server_script)
        
        # Make it executable
        os.chmod(self.output_dir / 'local_server.py', 0o755)

def main():
    """Main function"""
    base_url = "https://www.highlanderracing.org"
    
    print("🏁 Highlander Racing Website Cloner")
    print("=" * 50)
    
    # Allow custom output directory
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "highlander_racing_clone"
    
    cloner = WebsiteCloner(base_url, output_dir)
    cloner.clone_website()

if __name__ == "__main__":
    main()
