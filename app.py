import streamlit as st
import requests
from bs4 import BeautifulSoup
import cssutils
import re
import io
import base64
from urllib.parse import urljoin, urlparse
import os

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="🌐 Web Structure Cloner",
    page_icon="🧬",
    layout="wide"
)

st.title("🌐 Web Structure Cloner")
st.markdown("Paste any website URL, and I'll extract its CSS and layout to generate a custom Streamlit app template.")

# ---------- FUNCTIONS ----------
def fetch_html(url):
    """Fetch HTML content from URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        st.error(f"Failed to fetch URL: {e}")
        return None

def get_absolute_url(base, link):
    """Resolve relative URLs."""
    return urljoin(base, link)

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
        # We'll create a rule using the tag's selector (e.g., tag.class#id)
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
    return combined

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

if st.button("🚀 Extract Structure", type="primary"):
    if not url:
        st.warning("Please enter a valid URL.")
    else:
        with st.spinner("Fetching and analyzing page..."):
            html = fetch_html(url)
            if html:
                css = extract_css(url, html)
                if not css:
                    st.warning("No CSS extracted. The page might be heavily dynamic or require JavaScript.")
                else:
                    # Display extracted CSS length
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
st.caption("ℹ️ This tool extracts static CSS and HTML structure. It works best on simple, static websites. Dynamic content (JavaScript-generated) is not captured. For advanced styling, you can manually adjust the generated code.")
