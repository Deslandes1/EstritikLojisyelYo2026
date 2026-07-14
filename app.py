import streamlit as st
import requests
from bs4 import BeautifulSoup
import cssutils
import re
import io
import base64
import random
from urllib.parse import urljoin, urlparse
import os

# Attempt to import selenium – if not installed, fall back gracefully
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="🌐 Web Structure Cloner",
    page_icon="🧬",
    layout="wide"
)

st.title("🌐 Web Structure Cloner")
st.markdown("Paste any website URL, and I'll extract its CSS and layout to generate a custom Streamlit app template.")

# ---------- USER AGENTS FOR ROTATION ----------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ---------- FUNCTIONS ----------
def fetch_html_requests(url):
    """Fetch HTML using requests with realistic headers."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    try:
        session = requests.Session()
        session.headers.update(headers)
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        # If the response is compressed, requests automatically decompresses
        return resp.text
    except Exception as e:
        st.error(f"Requests fetch failed: {e}")
        return None

def fetch_html_selenium(url):
    """Fetch HTML using Selenium (headless Chrome) for dynamic content."""
    if not SELENIUM_AVAILABLE:
        st.error("Selenium is not installed. Please install it: `pip install selenium webdriver-manager`")
        return None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
        # Additional options to avoid detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get(url)
        driver.implicitly_wait(5)  # Wait for dynamic content
        html = driver.page_source
        driver.quit()
        return html
    except Exception as e:
        st.error(f"Selenium error: {e}")
        return None

def extract_css(url, html):
    """Extract all CSS from HTML (inline, internal, external)."""
    soup = BeautifulSoup(html, "html.parser")
    all_css = []

    # 1. Internal styles (style tags)
    for style_tag in soup.find_all("style"):
        css_text = style_tag.string
        if css_text:
            all_css.append(css_text)

    # 2. External stylesheets
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            abs_url = get_absolute_url(url, href)
            try:
                resp = requests.get(abs_url, timeout=10)
                if resp.status_code == 200:
                    all_css.append(resp.text)
            except Exception:
                pass

    # 3. Inline styles (extract from elements and create rules)
    inline_css = ""
    for tag in soup.find_all(style=True):
        style = tag["style"]
        # Build a simple selector based on tag, id, classes
        selector = tag.name
        if tag.get("id"):
            selector += f"#{tag['id']}"
        for cls in tag.get("class", []):
            selector += f".{cls}"
        inline_css += f"{selector} {{ {style} }}\n"
    if inline_css:
        all_css.append(inline_css)

    # Combine all CSS
    combined = "\n".join(all_css)
    # Remove @import and @charset (they might be absolute paths)
    combined = re.sub(r'@import\s+url\([^)]*\);', '', combined)
    combined = re.sub(r'@charset\s+"[^"]*";', '', combined)
    # Optionally remove relative urls that might break – leave as-is
    return combined

def get_absolute_url(base, link):
    """Resolve relative URLs."""
    return urljoin(base, link)

def generate_streamlit_code(url, css, html_sample):
    """Generate a Python script that uses the extracted CSS in a Streamlit app."""
    # Create a simplified layout: header, main, footer
    soup = BeautifulSoup(html_sample, "html.parser")
    
    # Try to find main sections
    header = soup.find("header")
    footer = soup.find("footer")
    main = soup.find("main") or soup.find("div", id="main") or soup.find("div", class_="main")
    
    # If not found, just use body content
    body = soup.body
    if body:
        # Clean body: keep only visible elements
        for script in body(["script", "noscript"]):
            script.decompose()
        html_content = str(body)
    else:
        html_content = "<div>No body content extracted.</div>"

    # Generate Streamlit code
    code = f"""import streamlit as st
import base64

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Cloned App", layout="wide")

# ---------- CUSTOM CSS ----------
# Paste the extracted CSS here
custom_css = \"\"\"{css}\"\"\"

st.markdown(f'<style>{{custom_css}}</style>', unsafe_allow_html=True)

# ---------- LAYOUT ----------
# Custom HTML layout (extracted from original page)
st.markdown(\"\"\"{html_content}\"\"\", unsafe_allow_html=True)

# You can also use Streamlit components to rebuild the layout:
# Example: columns, images, text, etc.
# See comments below.
"""
    # Add suggestions for manual adjustment
    code += """
# --------------------------------------------
# To adjust the layout, uncomment and modify:
# col1, col2 = st.columns([1, 2])
# with col1:
#     st.image("logo.png", width=150)
# with col2:
#     st.title("My Cloned App")
#     st.write("Add your content here.")
# --------------------------------------------
"""
    return code

# ---------- UI ----------
url = st.text_input("Enter the URL of the website to clone:", placeholder="https://example.com")

# Info box about limitations
st.info("""
💡 **Note:** Some websites (like Facebook, Instagram, and Twitter) block simple scraping requests.
- If you get a 400 error, try using the Selenium option below.
- For Facebook, you may need to use the official Graph API.
- This tool works best on static websites and blogs.
""")

use_selenium = st.checkbox("🌐 Use Selenium (slower, but handles JavaScript-heavy sites)", disabled=not SELENIUM_AVAILABLE)

if not SELENIUM_AVAILABLE and use_selenium:
    st.warning("Selenium is not installed. Please install it: `pip install selenium webdriver-manager`")

if st.button("🚀 Extract Structure", type="primary"):
    if not url:
        st.warning("Please enter a valid URL.")
    else:
        with st.spinner("Fetching and analyzing page..."):
            # Choose fetch method
            if use_selenium and SELENIUM_AVAILABLE:
                html = fetch_html_selenium(url)
            else:
                html = fetch_html_requests(url)
            
            if html:
                css = extract_css(url, html)
                if not css:
                    st.warning("No CSS extracted. The page might be heavily dynamic or require JavaScript.")
                else:
                    st.success(f"✅ Extracted {len(css)} characters of CSS.")
                    
                    # Generate code
                    code = generate_streamlit_code(url, css, html)
                    
                    # Show code in text area
                    st.subheader("📄 Generated Streamlit App Code")
                    st.code(code, language="python")
                    
                    # Download button
                    st.download_button(
                        label="⬇️ Download app.py",
                        data=code,
                        file_name="cloned_app.py",
                        mime="text/x-python"
                    )
                    
                    # Preview CSS
                    with st.expander("🎨 Extracted CSS (preview)"):
                        st.code(css[:2000] + ("..." if len(css) > 2000 else ""), language="css")
            else:
                st.error("Could not fetch the page. Please check the URL and try again.")

st.markdown("---")
st.caption("ℹ️ This tool extracts static CSS and HTML structure. It works best on simple, static websites. Dynamic content (JavaScript-generated) is not fully captured. For advanced styling, you can manually adjust the generated code.")
