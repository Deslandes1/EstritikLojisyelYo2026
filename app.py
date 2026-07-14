import streamlit as st
import requests
from bs4 import BeautifulSoup
import cssutils
import re
import io
import base64
import random
import os
import zipfile
import tempfile
from urllib.parse import urljoin, urlparse, unquote
from pathlib import Path

# Attempt Selenium – fallback if not installed
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
    page_title="🌐 Universal App Cloner",
    page_icon="🧬",
    layout="wide"
)

st.title("🧬 Universal App Cloner")
st.markdown("Clone the frontend, CSS, or full source code of any public app or GitHub repository.")

# ---------- USER AGENTS ----------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
]

# ---------- FUNCTIONS ----------

def fetch_html_requests(url):
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
        return resp.text
    except Exception as e:
        st.error(f"Requests fetch failed: {e}")
        return None

def fetch_html_selenium(url):
    if not SELENIUM_AVAILABLE:
        st.error("Selenium not installed. Install with: pip install selenium webdriver-manager")
        return None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get(url)
        driver.implicitly_wait(5)
        html = driver.page_source
        driver.quit()
        return html
    except Exception as e:
        st.error(f"Selenium error: {e}")
        return None

def extract_css(html, base_url):
    """Extract all CSS (inline, internal, external) and return combined CSS string."""
    soup = BeautifulSoup(html, "html.parser")
    all_css = []
    # Internal
    for style in soup.find_all("style"):
        if style.string:
            all_css.append(style.string)
    # External
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            abs_url = urljoin(base_url, href)
            try:
                resp = requests.get(abs_url, timeout=10)
                if resp.status_code == 200:
                    all_css.append(resp.text)
            except Exception:
                pass
    # Inline
    inline = ""
    for tag in soup.find_all(style=True):
        style = tag["style"]
        selector = tag.name
        if tag.get("id"):
            selector += f"#{tag['id']}"
        for cls in tag.get("class", []):
            selector += f".{cls}"
        inline += f"{selector} {{ {style} }}\n"
    if inline:
        all_css.append(inline)
    combined = "\n".join(all_css)
    combined = re.sub(r'@import\s+url\([^)]*\);', '', combined)
    combined = re.sub(r'@charset\s+"[^"]*";', '', combined)
    return combined

def extract_javascript(html, base_url):
    """Extract all JavaScript (inline and external) and return combined string."""
    soup = BeautifulSoup(html, "html.parser")
    all_js = []
    # Inline scripts
    for script in soup.find_all("script"):
        if script.string and not script.get("src"):
            all_js.append(script.string)
    # External scripts
    for script in soup.find_all("script", src=True):
        src = script["src"]
        if src:
            abs_url = urljoin(base_url, src)
            try:
                resp = requests.get(abs_url, timeout=10)
                if resp.status_code == 200:
                    all_js.append(resp.text)
            except Exception:
                pass
    return "\n".join(all_js)

def download_assets(html, base_url, output_dir):
    """Download images, fonts, etc. and replace URLs with local paths."""
    soup = BeautifulSoup(html, "html.parser")
    # We'll just download images for simplicity; fonts are trickier.
    # For a full clone, this is a large task. We'll generate a standalone HTML with embedded resources.
    # Instead, we'll embed CSS and JS inline and keep images as data URIs.
    # But to keep it simple, we'll just return the HTML with embedded CSS/JS.
    # We can also download images and convert to base64.
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if src.startswith("data:"):
            continue
        abs_url = urljoin(base_url, src)
        try:
            resp = requests.get(abs_url, timeout=10)
            if resp.status_code == 200:
                content_type = resp.headers.get('content-type', 'image/jpeg')
                b64 = base64.b64encode(resp.content).decode()
                img["src"] = f"data:{content_type};base64,{b64}"
        except Exception:
            pass
    return str(soup)

def generate_standalone_html(html, css, js, title="Cloned App"):
    """Produce a single HTML file with all CSS and JS inlined."""
    # Remove existing style and script tags that we are replacing
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()
    # Insert our inlined CSS and JS
    head = soup.head
    if not head:
        head = soup.new_tag("head")
        soup.html.insert(0, head)
    style_tag = soup.new_tag("style")
    style_tag.string = css
    head.append(style_tag)
    script_tag = soup.new_tag("script")
    script_tag.string = js
    head.append(script_tag)
    # Ensure proper DOCTYPE
    return f"<!DOCTYPE html>\n{str(soup)}"

def clone_github_repo(repo_url):
    """Clone a GitHub repository as a zip and return the bytes."""
    # Parse owner/repo from URL
    # Example: https://github.com/user/repo
    match = re.match(r'https?://github\.com/([^/]+)/([^/]+)/?', repo_url)
    if not match:
        return None, "Invalid GitHub URL. Use format: https://github.com/user/repo"
    owner, repo = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
    headers = {"Accept": "application/vnd.github.v3+json"}
    try:
        resp = requests.get(api_url, headers=headers, stream=True)
        if resp.status_code == 200:
            return resp.content, "Success"
        else:
            return None, f"GitHub API error: {resp.status_code}"
    except Exception as e:
        return None, f"Error: {e}"

# ---------- UI ----------
mode = st.radio(
    "Select cloning mode:",
    ["CSS Only", "Full Frontend Clone", "Clone GitHub Repository"],
    index=0,
    horizontal=True
)

url = st.text_input("Enter the URL:", placeholder="https://example.com or https://github.com/user/repo")

use_selenium = False
if mode in ["CSS Only", "Full Frontend Clone"]:
    use_selenium = st.checkbox("Use Selenium (for dynamic sites)", disabled=not SELENIUM_AVAILABLE)
    if not SELENIUM_AVAILABLE and use_selenium:
        st.warning("Selenium not installed. Falling back to requests.")

if st.button("🚀 Clone Now", type="primary"):
    if not url:
        st.warning("Please enter a URL.")
    else:
        if mode == "CSS Only":
            with st.spinner("Extracting CSS..."):
                html = fetch_html_selenium(url) if use_selenium else fetch_html_requests(url)
                if html:
                    css = extract_css(html, url)
                    if css:
                        st.success(f"✅ Extracted {len(css)} characters of CSS.")
                        # Generate a simple Streamlit app template
                        code = f"""import streamlit as st
custom_css = \"\"\"{css}\"\"\"
st.markdown(f'<style>{{custom_css}}</style>', unsafe_allow_html=True)
st.title("Cloned App")
st.write("Add your content here.")
"""
                        st.subheader("📄 Streamlit Code")
                        st.code(code, language="python")
                        st.download_button("⬇️ Download app.py", code, "cloned_app.py", "text/x-python")
                    else:
                        st.warning("No CSS extracted.")
                else:
                    st.error("Failed to fetch page.")

        elif mode == "Full Frontend Clone":
            with st.spinner("Cloning entire frontend (this may take a while)..."):
                html = fetch_html_selenium(url) if use_selenium else fetch_html_requests(url)
                if html:
                    css = extract_css(html, url)
                    js = extract_javascript(html, url)
                    # Download images and embed as base64
                    html_with_embedded_assets = download_assets(html, url, None)
                    standalone = generate_standalone_html(html_with_embedded_assets, css, js, title="Cloned App")
                    st.success("✅ Frontend cloned successfully!")
                    st.subheader("📄 Standalone HTML")
                    st.code(standalone[:2000] + ("..." if len(standalone) > 2000 else ""), language="html")
                    st.download_button("⬇️ Download index.html", standalone, "index.html", "text/html")
                else:
                    st.error("Failed to fetch page.")

        elif mode == "Clone GitHub Repository":
            with st.spinner("Cloning repository..."):
                zip_data, msg = clone_github_repo(url)
                if zip_data:
                    st.success("✅ Repository cloned successfully!")
                    st.download_button(
                        "⬇️ Download repository as .zip",
                        zip_data,
                        "repo.zip",
                        "application/zip"
                    )
                else:
                    st.error(msg)

st.markdown("---")
st.caption("⚠️ Limitations: Dynamic sites may not fully clone due to JavaScript execution. GitHub cloning works only for public repositories.")
