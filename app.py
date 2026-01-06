import streamlit as st
import feedparser
import time
from bs4 import BeautifulSoup
from datetime import datetime

# Page Config
st.set_page_config(page_title="AIニュースダッシュボード", page_icon="🤖", layout="wide")

# Custom CSS for Apple-style Card Layout
st.markdown("""
<style>
    /* Global Styles */
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #f5f5f7;
        background-color: #000000;
    }
    
    a.news-card-link {
        text-decoration: none;
        color: inherit;
        display: block;
    }

    /* Card Container */
    .news-card {
        background-color: #1c1c1e;
        border-radius: 18px;
        margin-bottom: 24px;
        border: none;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        overflow: hidden;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .news-card:hover {
        transform: scale(1.02);
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
        background-color: #2c2c2e;
        z-index: 10;
    }

    /* Thumbnail Image */
    .news-image-container {
        width: 100%;
        aspect-ratio: 16 / 9;
        overflow: hidden;
        background-color: #2c2c2e;
        position: relative;
    }
    
    .news-image {
        width: 100% !important;
        height: 100% !important;
        object-fit: cover !important;
        transition: transform 0.5s ease;
        display: block !important;
    }
    
    .news-card:hover .news-image {
        transform: scale(1.05);
    }
    
    /* Content Area */
    .news-content {
        padding: 20px;
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }
    
    /* Typography */
    .news-title {
        font-size: 20px;
        font-weight: 700;
        color: #f5f5f7;
        margin-bottom: 8px;
        line-height: 1.3;
        letter-spacing: -0.01em;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    .news-meta {
        font-size: 13px;
        color: #86868b;
        margin-bottom: 12px;
        display: flex;
        justify_content: space-between;
        align-items: center;
        font-weight: 500;
    }
    
    .news-summary {
        font-size: 15px;
        color: #d2d2d7;
        margin-bottom: 16px;
        line-height: 1.5;
        flex-grow: 1;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    .read-more {
        color: #2997ff;
        font-weight: 600;
        font-size: 14px;
        text-align: right;
        margin-top: auto;
    }
    
    /* Fix for anchor wrapping div in Streamlit */
    a:hover {
        text-decoration: none;
    }
    
    /* Sidebar customization */
    section[data-testid="stSidebar"] {
        background-color: #1c1c1e;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }
    /* Force white text in sidebar elements */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] .stMarkdown, 
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] .stRadio div[role='radiogroup'] p {
        color: #f5f5f7 !important;
    }
    /* Input text should be black */
    section[data-testid="stSidebar"] .stTextInput input {
        color: #000000 !important;
        background-color: #ffffff !important;
    }
    /* Specific fix for labels if not caught above */
    section[data-testid="stSidebar"] label {
        color: #f5f5f7 !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to extract image and clean HTML from summary
def parse_summary(html_content):
    if not html_content:
        return "", ""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Extract Image from HTML
    img_tag = soup.find('img')
    img_src = img_tag['src'] if img_tag else ""
    
    # Get Text
    text = soup.get_text(separator=' ', strip=True)
    return text, img_src

# Upgrade Bing Thumbnail Quality
def get_high_res_image_url(url):
    if not url:
        return ""
    # Check if it's a Bing Thumbnail
    if "bing.com/th" in url:
        # Request larger size (e.g., 800x450 for 16:9 high quality)
        # c=7: Smart crop, rs=1: Resize
        return f"{url}&w=800&h=450&c=7&rs=1"
    return url

# Sidebar
with st.sidebar:
    st.title("設定")
    
    # Category Selection
    category_options = {
        "検索 (キーワード)": "SEARCH",
        "トップニュース": "HEADLINES",
        "テクノロジー": "TECHNOLOGY",
        "ビジネス": "BUSINESS",
        "科学": "SCIENCE",
        "エンタメ": "ENTERTAINMENT",
        "スポーツ": "SPORTS",
        "健康": "HEALTH"
    }
    selected_category_label = st.selectbox("カテゴリー選択", list(category_options.keys()))
    selected_category_code = category_options[selected_category_label]

    if selected_category_code == "SEARCH":
        query = st.text_input("検索キーワード", value="Artificial Intelligence")
    else:
        query = selected_category_label # Display name mapping for title
    
    st.divider()
    
    # Filtering & Sorting
    st.subheader("表示オプション")
    filter_keyword = st.text_input("結果を絞り込む", placeholder="例: Google, OpenAI...")
    sort_order = st.radio("並び替え", ["新しい順", "古い順"], horizontal=True)
    
    st.caption("News provided by Google News")

# Main Content
st.title(f"{query}")

# Fetch RSS
def fetch_news(category_code, query_text):
    # Switch to Bing News for Thumbnails support
    base_url = "https://www.bing.com/news"
    # Added &cc=JP for Japanese content context
    params = "&format=rss&cc=JP" 
    
    if category_code == "SEARCH":
        encoded_query = query_text.replace(" ", "%20")
        url = f"{base_url}/search?q={encoded_query}{params}"
    elif category_code == "HEADLINES":
        # "Top News" in Japanese to get results
        url = f"{base_url}/search?q=%E3%83%88%E3%83%83%E3%83%97%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9{params}"
    else:
        # Bing uses search for topics effectively
        # We use the category label/keyword
        encoded_query = query_text.replace(" ", "%20")
        url = f"{base_url}/search?q={encoded_query}{params}"
        
    feed = feedparser.parse(url)
    return feed.entries

# Determine what to pass to fetch_news
if selected_category_code == "SEARCH":
    fetch_arg = query
elif selected_category_code == "HEADLINES":
    fetch_arg = ""
else:
    # Pass the category name itself as query for Bing
    fetch_arg = selected_category_label

if selected_category_code != "SEARCH" or query:
    with st.spinner(f"ニュースを読み込み中..."):
        entries = fetch_news(selected_category_code, fetch_arg)
        
    if entries:
        # 1. Parsing & Filtering
        processed_entries = []
        for entry in entries:
            title = entry.get('title', '')
            raw_summary = entry.get('summary', '')
            
            # 1. Try 'news_image' (Bing Specific)
            img_src = entry.get('news_image', '')
            
            # 2. If no image, try extracting from Description HTML
            summary_text, html_img_src = parse_summary(raw_summary)
            if not img_src:
                img_src = html_img_src
            
            # 3. If no image, try 'media_content'
            if not img_src and 'media_content' in entry:
                media = entry['media_content']
                if media and isinstance(media, list) and len(media) > 0:
                    img_src = media[0].get('url', '')
            
            # 4. If no image, try 'media_thumbnail'
            if not img_src and 'media_thumbnail' in entry:
                thumbs = entry['media_thumbnail']
                if thumbs and isinstance(thumbs, list) and len(thumbs) > 0:
                    img_src = thumbs[0].get('url', '')

            # 5. If no image, try 'enclosures'
            if not img_src and 'enclosures' in entry:
                for enc in entry.enclosures:
                    if enc.type.startswith('image'):
                        img_src = enc.href
                        break

            # Upgrade Image Quality
            img_src = get_high_res_image_url(img_src)

            # Filter Logic
            if filter_keyword:
                if filter_keyword.lower() not in title.lower() and filter_keyword.lower() not in summary_text.lower():
                    continue
            
            # Formatting Date
            published = entry.get('published', '')
            
            # Source extraction (Bing uses 'news_source' as string, Google used dict)
            # Fix for AttributeError: 'str' object has no attribute 'get'
            source = entry.get('news_source') or entry.get('source', {}).get('title', '')
            
            processed_entries.append({
                'title': title,
                'link': entry.get('link', '#'),
                'published': published,
                'published_parsed': entry.get('published_parsed', time.localtime(0)),
                'summary': summary_text,
                'img_src': img_src,
                'source': source
            })

        st.caption(f"{len(processed_entries)} 件の記事が見つかりました")

        # 2. Sort
        try:
            processed_entries.sort(
                key=lambda x: x['published_parsed'], 
                reverse=(sort_order == "新しい順")
            )
        except:
            pass

        # 3. Display
        cols = st.columns(3) # Changed to 3 columns for better Apple-like card density on wide screens
        
        for i, entry in enumerate(processed_entries):
            col = cols[i % 3]
            with col:
                # Render Card
                # If image exists, show it. Otherwise show nothing (or a placeholder color/pattern could be added)
                # Force inline styles for image to ensure it covers
                image_html = f'<div class="news-image-container"><img src="{entry["img_src"]}" class="news-image" style="width:100% !important; height:100% !important; object-fit:cover !important;" onerror="this.style.display=\'none\'"></div>' if entry["img_src"] else '<div class="news-image-container" style="display:none;"></div>'
                
                # Card HTML Structure
                st.markdown(f"""
                <a href="{entry['link']}" target="_blank" class="news-card-link">
                    <div class="news-card">
                        {image_html}
                        <div class="news-content">
                            <div class="news-title">{entry['title']}</div>
                            <div class="news-meta">
                                <span>{entry['source']}</span>
                                <span>{entry['published']}</span>
                            </div>
                            <div class="news-summary">{entry['summary'][:150]}...</div>
                            <div class="read-more">Read Story ↗</div>
                        </div>
                    </div>
                </a>
                """, unsafe_allow_html=True)
    else:
        st.warning("ニュースが見つかりませんでした。")
else:
    st.info("左側のサイドバーでキーワードを入力してください。")
