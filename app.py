import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as stx

# --- Cookie Management (Library-based) ---
# Initialize CookieManager with a unique key for stability
cookie_manager = stx.CookieManager(key="cookie_manager_v1")

def set_cookie_js(name, value, days=2):
    """Set a cookie using both Manager and Raw JS for maximum compatibility."""
    import datetime
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    
    # 1. Try CookieManager
    cookie_manager.set(name, value, expires_at=expires, key=f"set_{name}")
    
    # 2. Try Raw JS Fallback (especially for iframes/local mix)
    # Use lowercase for case-insensitivity
    is_https = st.context.headers.get("X-Forwarded-Proto", "").lower() == "https"
    secure_attr = "SameSite=None; Secure" if is_https else "SameSite=Lax"
    
    max_age = days * 24 * 60 * 60
    # We set multiple variations to see what the browser accepts
    js_code = f"""
        <script>
        // Strategy A: Best for iframes (HTTPS)
        document.cookie = "{name}={value}; Max-Age={max_age}; Path=/; SameSite=None; Secure";
        // Strategy B: Best for Local (HTTP)
        document.cookie = "{name}_{value}_lax={value}; Max-Age={max_age}; Path=/; SameSite=Lax";
        // Strategy C: Absolute Simple
        document.cookie = "{name}_{value}_simple={value}; Max-Age={max_age}; Path=/;";
        console.log("Multi-strategy cookie set attempted for {name}");
        </script>
    """
    components.html(js_code, height=0)

def delete_cookie_js(name):
    """Delete a cookie."""
    cookie_manager.delete(name, key=f"del_{name}")
    js_code = f"""
        <script>
        document.cookie = "{name}=; Max-Age=0; Path=/;";
        </script>
    """
    components.html(js_code, height=0)
import feedparser
import time
import pandas as pd
from bs4 import BeautifulSoup
import datetime
import requests
import re
import base64
import difflib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote, urlparse
import random
# Database module
import database as db

def get_remote_ip():
    """Get remote user IP from headers."""
    try:
        # Check various headers for IP
        headers = st.context.headers
        for header in ["X-Forwarded-For", "X-Real-IP", "Remote-Addr"]:
            val = headers.get(header)
            if val:
                return val.split(",")[0].strip()
        return "0.0.0.0"
    except:
        return "0.0.0.0"

# Initialize DB
db.init_db()

# Page Config

def setup_touch_icon(image_path="app_icon.png"):
    """Injects Apple Touch Icon using base64 encoding."""
    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        b64_img = base64.b64encode(img_bytes).decode('utf-8')
        # mime type detection (simple)
        mime = "image/png"
        
        st.markdown(
            f"""
            <link rel="apple-touch-icon" href="data:{mime};base64,{b64_img}">
            <link rel="icon" href="data:{mime};base64,{b64_img}">
            """,
            unsafe_allow_html=True
        )
    except Exception as e:
        pass # Fail silently if icon missing

# --- Setup & Config ---
st.set_page_config(page_title="AI News Pro", page_icon="🍌", layout="wide")
setup_touch_icon()

ALL_SOURCES = [
    "Bing News", "Yahoo! ニュース", "ライブドアニュース", "NHK ニュース", 
    "Google News", "Gigazine", "ITmedia", "CNET Japan", 
    "TechCrunch Japan", "Qiita", "Zenn", "ナタリー"
]

# --- Session State ---
if 'user' not in st.session_state:
    st.session_state.user = None

# Try to load persistent session if not logged in
if st.session_state.user is None:
    # 1. Try CookieManager (Standard for library use)
    token = cookie_manager.get('session_token')
    # 2. Try native st.context.cookies (Fallback if component slow to load)
    if not token:
        token = st.context.cookies.get('session_token')
        
    if token:
        ip = get_remote_ip()
        result = db.verify_persistent_session(token, ip)
        if "@" in str(result): # Check if result is an email
            st.session_state.user = result
            load_user_session()
            time.sleep(0.1) 
            st.rerun() 
        else:
            # Result is an error code like TOKEN_NOT_FOUND or IP_MISMATCH
            # We don't delete automatically here to avoid DuplicateElementKey
            # when the Reset button also triggers.
            pass


# Logic to load user data if logged in
def load_user_session():
    if st.session_state.user:
        username = st.session_state.user
        st.session_state.recommendation_keywords = db.load_user_data(username, 'keywords', [])
        st.session_state.bookmarks = db.load_user_data(username, 'bookmarks', [])
        saved_theme = db.load_user_data(username, 'theme', 'Dark')
        st.session_state.theme = saved_theme
        st.session_state.mute_words = db.load_user_data(username, 'mute_words', [])

if 'theme' not in st.session_state:
    st.session_state.theme = 'Dark'
if 'bookmarks' not in st.session_state:
    st.session_state.bookmarks = []
if 'recommendation_keywords' not in st.session_state:
    st.session_state.recommendation_keywords = []
if 'date_filter' not in st.session_state:
    st.session_state.date_filter = "すべて"
if 'mute_words' not in st.session_state:
    st.session_state.mute_words = []

# Call load_user_session after initial setup
load_user_session()

# --- Theme Configuration ---
theme_colors = {
    'Dark': {
        'bg': '#000000',
        'sidebar_bg': '#161617',
        'card_bg': '#000000',
        'text': '#ffffff',
        'sub_text': '#a1a1a6',
        'border': '#333336',
        'button_bg': '#1c1c1e',
        'button_text': '#ffffff',
        'accent': '#ffffff',
        'input_bg': '#1c1c1e',
        'shadow': 'none'
    },
    'Light': {
        'bg': '#ffffff',
        'sidebar_bg': '#f5f5f7',
        'card_bg': '#ffffff',
        'text': '#1d1d1f',
        'sub_text': '#6e6e73',
        'border': '#d2d2d7',
        'button_bg': '#f5f5f7',
        'button_text': '#1d1d1f',
        'accent': '#000000',
        'input_bg': '#ffffff',
        'shadow': 'none'
    }
}
c = theme_colors[st.session_state.theme]

# --- Helper Functions ---
def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = ' '.join(cleantext.split())
    return cleantext

def parse_summary(html_content):
    if not html_content: return "", ""
    soup = BeautifulSoup(html_content, "html.parser")
    img_tag = soup.find('img')
    img_src = img_tag['src'] if img_tag else ""
    text = clean_html(html_content)
    return text, img_src

def get_high_res_image_url(url):
    if not url: return ""
    if "bing.com/th" in url: return f"{url}&w=800&h=450&c=7&rs=1"
    return url

@st.cache_data(ttl=3600)
def fetch_og_image(url):
    if not url or url == "#": return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        og = soup.find('meta', property='og:image')
        if og: return og.get('content')
    except: pass
    return ""

def send_auth_email(target_email, subject, body):
    """Send an authentication email using Sakura Server SMTP."""
    # Check if SMTP secrets are configured
    if 'smtp' not in st.secrets:
        st.error("SMTP設定が見つかりません。`st.secrets` を設定してください。")
        return False
    
    try:
        conf = st.secrets['smtp']
        smtp_server = conf['host']
        smtp_port = conf['port']
        sender_email = conf['user']
        sender_password = conf['password']
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email # Simplified to avoid rejection
        msg['To'] = target_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect and send
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        server.login(sender_email, sender_password)
        # Explicitly specify envelope addresses
        server.send_message(msg, from_addr=sender_email, to_addrs=[target_email])
        server.quit()
        return True
    except Exception as e:
        if "5.7.1" in str(e):
             st.error(f"メール送信エラー (5.7.1): さくらサーバーの「国外IPアドレスフィルター」が有効な可能性があります。コントロールパネルから解除してください。")
        else:
             st.error(f"メール送信エラー: {str(e)}")
        return False


def get_remote_ip():
    """Get remote user IP from headers."""
    try:
        # Check various headers for IP
        headers = st.context.headers
        for header in ["X-Forwarded-For", "X-Real-IP", "Remote-Addr"]:
            val = headers.get(header)
            if val:
                return val.split(",")[0].strip()
        return "0.0.0.0"
    except:
        return "0.0.0.0"

# --- Sidebar (Moved up for visibility during login) ---
with st.sidebar:
    st.markdown(f"<h1 style='color: {c['text']}; display: flex; align-items: center; gap: 10px;'><span style='font-size: 1.5em;'>🍌</span> AI News Pro</h1>", unsafe_allow_html=True)
    
    if st.session_state.user:
        st.caption(f"Logged in: {st.session_state.user}")
        if st.button("ログアウト", use_container_width=True):
            logout()
            st.rerun()
    else:
        st.caption("Guest Mode")
        st.info("ゲストモードでは設定は保存されません")
        if st.button("ログイン / 登録", use_container_width=True):
            st.session_state.guest_mode = False
            st.rerun()

    # --- Debug: Persistence Info (Only for testing) ---
    with st.expander("🔍 Debug: ログイン維持状態", expanded=True):
        ip = get_remote_ip()
        st.write(f"Detected IP: `{ip}`")
        st.write("Context Cookies:", st.context.cookies)
        
        token_mgr = cookie_manager.get('session_token')
        token_ctx = st.context.cookies.get('session_token')
        
        st.write(f"Manager Token: `{'Found' if token_mgr else 'None'}`")
        st.write(f"Context Token: `{'Found' if token_ctx else 'None'}`")
        
        if token_mgr or token_ctx:
            token = token_mgr or token_ctx
            st.write(f"Active Token: `{token[:10]}...`")
            # Verify manually in debug view
            user_check = db.verify_persistent_session(token, ip)
            if "@" in str(user_check):
                st.success(f"DB Verification: ✅ {user_check}")
            else:
                st.error(f"DB Verification: ❌ {user_check}")
        else:
            st.warning("No session token found in browser.")
            
        if st.button("🔄 Force Refresh (Page Rerun)", key="debug_refresh"):
            st.rerun()
            
        if st.button("🗑️ Reset Persistence (Delete Bad Cookie)", key="debug_clear"):
            delete_cookie_js('session_token')
            st.success("Cookie deletion requested. Please refresh if token persists.")
            st.rerun()

        if st.button("🧪 Test Cookie (Set Multi-Strategy)", key="debug_test"):
            set_cookie_js('debug_test', 'v1', days=1)
            st.info("Set 3 cookies: debug_test, debug_test_v1_lax, debug_test_v1_simple. Please refresh.")
            st.rerun()

    st.warning("⚠️ **Cookieが保存されない場合:**\n\nブラウザの設定で「サードパーティのCookieをブロックする」が有効になっている可能性があります。Streamlit Cloudはiframe内で動作するため、この設定を解除するか、ログインURLバーにある「目のアイコン」をクリックして許可してください。")

    st.markdown("### Settings")
    theme_btn = st.radio("テーマ選択", ["Dark", "Light"], horizontal=True, index=0 if st.session_state.theme == "Dark" else 1)
    if theme_btn != st.session_state.theme:
        st.session_state.theme = theme_btn
        # Save theme setting
        if st.session_state.user:
            db.save_user_data(st.session_state.user, 'theme', theme_btn)
        st.rerun()

    st.divider()

    # Mute Settings
    with st.expander("ミュート設定"):
        st.caption("指定した単語を含む記事を非表示にします")
        def add_mute():
            new_m = st.session_state.new_mute_input
            if new_m and new_m not in st.session_state.mute_words:
                st.session_state.mute_words.append(new_m)
                st.session_state.new_mute_input = ""
                if st.session_state.user:
                    db.save_user_data(st.session_state.user, 'mute_words', st.session_state.mute_words)
        
        st.text_input("除外したい単語", key="new_mute_input", on_change=add_mute)
        
        if st.session_state.mute_words:
            st.markdown("---")
            for i, mw in enumerate(st.session_state.mute_words):
                col1, col2 = st.columns([3, 1])
                col1.markdown(f"🚫 {mw}")
                if col2.button("✕", key=f"del_mute_{i}", use_container_width=True):
                    st.session_state.mute_words.pop(i)
                    if st.session_state.user:
                        db.save_user_data(st.session_state.user, 'mute_words', st.session_state.mute_words)
                    st.rerun()

    # Define news sources
    news_sources = [
        "⚡ 総合トップ",
        "Bing News",
        "Yahoo! ニュース", 
        "ライブドアニュース", 
        "NHK ニュース",
        "Google News", 
        "Gigazine", 
        "ITmedia",
        "CNET Japan",
        "TechCrunch Japan",
        "Qiita",
        "Zenn",
        "ナタリー"
    ]

    source = st.selectbox(
        "ニュースソース", 
        news_sources, 
        index=0, # Set "⚡ 総合トップ" as default
        key="news_source_select"
    )

    cats = {}
    if source == "⚡ 総合トップ":
        cats = {"最新トレンド": "HEADLINES"}
    elif source == "Yahoo! ニュース":
        cats = {
            "主要": "HEADLINES", "IT・科学": "TECHNOLOGY", "経済": "BUSINESS", "国際": "International", 
            "エンタメ": "Entertainment", "スポーツ": "Sports", "国内": "Domestic", "ライフ": "Life", 
            "地域": "Local"
        }
    elif source == "NHK ニュース":
        cats = {
            "主要": "HEADLINES", "社会": "Social", "政治": "Politics", "国際": "International", 
            "経済": "Economy", "科学・文化": "Science", "スポーツ": "Sports", "地域": "Local"
        }
    elif source == "Google News":
        cats = {
            "トップ": "HEADLINES", "テクノロジー": "TECHNOLOGY", "ビジネス": "BUSINESS", "国際": "International", 
            "エンタメ": "Entertainment", "スポーツ": "Sports", "科学": "Science", "健康": "Health"
        }
    elif source == "ITmedia":
        cats = {
            "総合": "ALL", "モバイル": "MOBILE", "エンタープライズ": "ENTERPRISE", 
            "PC USER": "PCUSER", "ビジネスオンライン": "BUSINESS"
        }
    elif source in ["Qiita", "Zenn"]:
        cats = {"トレンド": "HEADLINES"}
    elif source == "ナタリー":
        cats = {
            "音楽": "MUSIC", "映画": "MOVIE", "お笑い": "COMEDY", "コミック": "COMIC"
        }
    elif source in ["CNET Japan", "TechCrunch Japan", "Gigazine", "ライブドアニュース"]:
        cats = {"トップ": "HEADLINES"}
    elif source == "Bing News":
        cats = {
            "トップ": "HEADLINES", "ビジネス": "Business", "テクノロジー": "Technology", 
            "エンタメ": "Entertainment", "政治": "Politics", "科学": "Science", 
            "健康": "Health", "スポーツ": "Sports", "国際": "World", "国内": "Japan"
        }
        
    cat_label = st.selectbox("カテゴリー", list(cats.keys()), key=f"cat_select_{source}")
    cat_code = cats[cat_label]

    st.divider()
    st.markdown("### おすすめ設定")

    # Keyword management with Enter key support
    def add_keyword():
        new_kw = st.session_state.new_keyword_input
        if new_kw and new_kw not in st.session_state.recommendation_keywords:
                if len(st.session_state.recommendation_keywords) < 5:
                    st.session_state.recommendation_keywords.append(new_kw)
                    st.session_state.new_keyword_input = ""  # Clear input
                    # Save to DB
                    if st.session_state.user:
                        db.save_user_data(st.session_state.user, 'keywords', st.session_state.recommendation_keywords)
                else:
                    st.warning("登録できるキーワードは5つまでです")
        elif new_kw in st.session_state.recommendation_keywords:
            st.warning("そのキーワードは既に登録されています")

    new_keyword = st.text_input(
        "興味のあるキーワードを追加（Enterで追加）", 
        key="new_keyword_input", 
        placeholder="例: AI, Python, 経済",
        on_change=add_keyword
    )

    # Display current keywords
    if st.session_state.recommendation_keywords:
        st.markdown("**登録済みキーワード:**")
        for i, kw in enumerate(st.session_state.recommendation_keywords):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"• {kw}")
            with col2:
                if st.button("✕", key=f"remove_kw_{i}", use_container_width=True):
                    st.session_state.recommendation_keywords.pop(i)
                    # Save to DB
                    if st.session_state.user:
                        db.save_user_data(st.session_state.user, 'keywords', st.session_state.recommendation_keywords)
                    st.rerun()

@st.cache_data(ttl=300)
def fetch_news(source, category_code, query_text):
    """Fetch and parse news from RSS feeds."""
    
    # --- Global Top Aggregation Logic ---
    if source == "⚡ 総合トップ":
        # Aggregate from EVERY available source
        source_configs = {
            "Bing News": "HEADLINES",
            "Yahoo! ニュース": "HEADLINES",
            "ライブドアニュース": "HEADLINES",
            "Google News": "HEADLINES",
            "NHK ニュース": "HEADLINES",
            "Gigazine": "HEADLINES",
            "ITmedia": "ALL",
            "CNET Japan": "HEADLINES",
            "TechCrunch Japan": "HEADLINES",
            "Qiita": "HEADLINES",
            "Zenn": "HEADLINES",
            "ナタリー": "MUSIC"
        }
        
        all_items = []
        seen_links = set()
        
        for src, cat in source_configs.items():
            try:
                items = fetch_news(src, cat, "")
                for item in items:
                    if item['link'] not in seen_links:
                        all_items.append(item)
                        seen_links.add(item['link'])
            except:
                continue
        
        # Sort by published date (newest first)
        all_items.sort(key=lambda x: x['published'], reverse=True)
        
        # Take top 50
        return all_items[:50]

    # --- Standard Source Logic ---
    url = ""
    if source == "Yahoo! ニュース":
        # Using /categories/ for most to get 50 articles and fix "Life"
        mapping = {
            "HEADLINES": "topics/top-picks.xml",
            "TECHNOLOGY": "categories/it.xml",
            "BUSINESS": "categories/business.xml",
            "International": "categories/world.xml",
            "Entertainment": "categories/entertainment.xml",
            "Sports": "categories/sports.xml",
            "Science": "topics/science.xml", # No category for science
            "Local": "categories/local.xml",
            "Domestic": "categories/domestic.xml",
            "Life": "categories/life.xml"
        }
        url = f"https://news.yahoo.co.jp/rss/{mapping.get(category_code, 'topics/top-picks.xml')}"
    elif source == "NHK ニュース":
        mapping = {
            "HEADLINES": "cat0.xml", "Social": "cat1.xml", "Politics": "cat4.xml",
            "International": "cat6.xml", "Economy": "cat5.xml", "Science": "cat3.xml", "Sports": "cat2.xml",
            "Local": "cat9.xml"
        }
        url = f"https://www.nhk.or.jp/rss/news/{mapping.get(category_code, 'cat0.xml')}"
    elif source == "Bing News":
        # Map category codes to Japanese search terms
        bing_map = {
            "HEADLINES": "トップニュース", "Business": "経済", "Technology": "テクノロジー",
            "Entertainment": "工ンタメ", "Politics": "政治", "Science": "科学",
            "Health": "健康", "Sports": "スポーツ", "World": "国際", "Japan": "国内トップ"
        }
        # Use query_text if provided (global search), otherwise use category mapping
        q = query_text if query_text else bing_map.get(category_code, "トップニュース")
        url = f"https://www.bing.com/news/search?q={quote(q)}&format=rss&cc=JP&setLang=ja-JP"
    elif source == "Google News":
        # Mapping standard labels to working Google News Topic IDs
        g_map = {
            "HEADLINES": "", 
            "TECHNOLOGY": "TECHNOLOGY",
            "BUSINESS": "BUSINESS",
            "International": "WORLD",
            "Entertainment": "ENTERTAINMENT",
            "Sports": "SPORTS",
            "Science": "SCIENCE",
            "Health": "HEALTH"
        }
        params = "hl=ja&gl=JP&ceid=JP:ja"
        if category_code == "SEARCH": 
            url = f"https://news.google.com/rss/search?q={quote(query_text)}&{params}"
        elif category_code == "HEADLINES": 
            url = f"https://news.google.com/rss?{params}"
        else: 
            # Use the more stable /headlines/section/topic/ format
            topic_id = g_map.get(category_code, "")
            if topic_id:
                url = f"https://news.google.com/rss/headlines/section/topic/{topic_id}?{params}"
            else:
                url = f"https://news.google.com/rss?{params}"
    elif source == "Qiita":
        url = f"https://qiita.com/tags/{quote(query_text) if category_code != 'HEADLINES' else 'Python'}/feed"
    elif source == "Zenn":
        url = f"https://zenn.dev/topics/{quote(query_text.lower()) if category_code != 'HEADLINES' else 'tech'}/feed"
    elif source == "ITmedia":
        it_map = {
            "ALL": "itmedia_all.xml", "MOBILE": "mobile.xml", "ENTERPRISE": "enterprise.xml",
            "PCUSER": "pcuser.xml", "BUSINESS": "business.xml"
        }
        url = f"https://rss.itmedia.co.jp/rss/2.0/{it_map.get(category_code, 'itmedia_all.xml')}"
    elif source == "ナタリー":
        natalie_map = {
            "MUSIC": "music", "MOVIE": "eiga", "COMEDY": "owarai", "COMIC": "comic"
        }
        category = natalie_map.get(category_code, "music")
        url = f"https://natalie.mu/{category}/feed/news"
    elif source == "CNET Japan":
        url = "https://japan.cnet.com/rss/index.rdf"
    elif source == "TechCrunch Japan":
        url = "https://techcrunch.com/tag/japan/feed/"
    elif source == "Gigazine":
        url = "https://gigazine.net/news/rss_2.0/"
    elif source == "ライブドアニュース":
        url = "https://news.livedoor.com/topics/rss/top.xml"

    if not url: return []
    try:
        feed = feedparser.parse(url)
        processed = []
        for entry in feed.entries:
            title = entry.get('title', 'No Title')
            link = entry.get('link', '#')
            raw_sum = entry.get('summary', '') or entry.get('description', '') or entry.get('content', [{'value': ''}])[0].get('value', '')
            img = entry.get('news_image', '') or entry.get('media_thumbnail', [{'url':''}])[0].get('url','')
            if not img:
                 for enc in entry.get('enclosures', []):
                    if 'image' in enc.get('type', '') or any(ext in enc.get('href', '').lower() for ext in ['.jpg','.jpeg','.png','.webp']):
                        img = enc.get('href', '')
                        break
            summary_text, html_img = parse_summary(raw_sum)
            if not img: img = html_img
            # Parse date for reliable sorting
            pub_date_raw = entry.get('published', '')
            pub_date_formatted = pub_date_raw[:16] # Fallback
            if 'published_parsed' in entry and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6])
                    pub_date_formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass

            processed.append({
                'title': title, 'link': link, 'summary': summary_text, 
                'img_src': get_high_res_image_url(img), 'source': source, 
                'id': link, 'published': pub_date_formatted
            })
        return processed
    except: return []

def calculate_article_score(article, keywords):
    """Calculate relevance score for an article based on keywords and freshness."""
    if not keywords:
        return 0
    
    score = 0
    title_lower = article['title'].lower()
    summary_lower = article['summary'].lower()
    
    # Keyword matching (max 50 points)
    keyword_matched = False
    for keyword in keywords:
        kw_lower = keyword.lower()
        if kw_lower in title_lower:
            score += 30
            keyword_matched = True
        elif kw_lower in summary_lower:
            score += 20
            keyword_matched = True
    
    # Only add freshness bonus if at least one keyword matched
    if keyword_matched:
        score += 15  # Freshness bonus for relevant articles
    
    return score

def get_recommended_articles(keywords):
    """
    Fetch articles by actively searching for each keyword in Bing and Google News.
    This ensures specific topics (e.g., 'Frieren', 'AI') are found even if not in headlines.
    """
    if not keywords:
        return []
    
    all_articles = []
    seen_links = set()
    
    # Active search for each keyword
    # Limiting to Bing & Google for best search performance
    search_targets = ["Bing News", "Google News"]
    
    progress_text = st.empty()
    
    for i, kw in enumerate(keywords):
        # Determine source rotation or query both?
        # Querying both for max recall.
        for source in search_targets:
            try:
                # Use cached fetch
                items = fetch_news(source, "SEARCH", kw)
                for item in items:
                    if item['link'] not in seen_links:
                        # Calculate score immediately
                        score = calculate_article_score(item, keywords)
                        if score > 0:
                            all_articles.append((score, item))
                            seen_links.add(item['link'])
            except Exception:
                continue
                
    # Sort by score (descending)
    all_articles.sort(reverse=True, key=lambda x: x[0])
    
    # Return top items
    return all_articles[:50]

def get_search_results(query):
    """Search for a keyword across multiple sources."""
    if not query: return []
    
    search_sources = [
        ("Bing News", "SEARCH"),
        ("Google News", "SEARCH"),
        ("Qiita", "SEARCH"),
        ("Zenn", "SEARCH")
    ]
    
    results = []
    seen_links = set()
    
    for source, cat_code in search_sources:
        try:
            articles = fetch_news(source, cat_code, query)
            for article in articles:
                if article['link'] not in seen_links:
                    results.append(article)
                    seen_links.add(article['link'])
        except:
            continue
            
    return results

# --- Content Optimization Logic ---
def is_similar(a, b, threshold=0.6):
    """Check if two titles are similar using SequenceMatcher."""
    return difflib.SequenceMatcher(None, a, b).ratio() > threshold

def group_articles(articles):
    """Group similar articles together."""
    groups = []
    # articles must be sorted by date or score before grouping for best results
    # We assume they are already sorted.
    
    processed_indices = set()
    
    for i, article in enumerate(articles):
        if i in processed_indices:
            continue
            
        # Start a new group
        current_group = [article]
        processed_indices.add(i)
        
        # Look ahead for similar articles
        for j in range(i + 1, len(articles)):
            if j in processed_indices:
                continue
            
            other = articles[j]
            # Check similarity
            if is_similar(article['title'], other['title']):
                current_group.append(other)
                processed_indices.add(j)
        
        groups.append(current_group)
            
    return groups

def filter_muted_articles(articles, mute_words):
    """Filter out articles containing mute words."""
    if not mute_words:
        return articles
    
    filtered = []
    for item in articles:
        # Check title and summary
        text_to_check = (item['title'] + " " + item['summary']).lower()
        if not any(mw.lower() in text_to_check for mw in mute_words):
            filtered.append(item)
            
    return filtered


# --- Design ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: {c['bg']};
    }}
    
    header[data-testid="stHeader"] svg {{
        fill: #888888 !important;
        opacity: 0.8;
    }}
    header[data-testid="stHeader"] button {{
        color: #888888 !important;
    }}
    header[data-testid="stHeader"] {{ background-color: transparent !important; }}
    
    /* Requested Header Background Fix */
    .st-emotion-cache-14vh5up {{
        background-color: {c['bg']} !important;
    }}
    
    [data-testid="stMain"] {{
        color: {c['text']} !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: {c['sidebar_bg']} !important;
        border-right: 1px solid {c['border']};
    }}
    
    /* Global Sidebar Text/Headings/Links */
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{
        color: {c['text']} !important;
        font-weight: 600 !important;
    }}
    
    /* Fix for Logged in / Links in sidebar */
    [data-testid="stSidebar"] a {{
        color: {c['sub_text']} !important;
        text-decoration: underline;
    }}

    /* Expander / Accordion Styling Fix */
    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        border: 1px solid {c['border']} !important;
        border-radius: 8px !important;
        background-color: transparent !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        background-color: transparent !important;
        color: {c['text']} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        background-color: {c['input_bg']} !important;
    }}
    /* SVG icon in expander */
    [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{
        fill: {c['text']} !important;
    }}

    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
        background-color: {c['input_bg']} !important;
        border: 1px solid {c['border']} !important;
        border-radius: 8px !important;
    }}
    /* Ensure visible text color in selectboxes and inputs */
    div[data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="input"] input {{
        color: {c['text']} !important;
        -webkit-text-fill-color: {c['text']} !important;
    }}
    /* Placeholder contrast */
    ::placeholder {{
        color: {c['sub_text']} !important;
        opacity: 0.8 !important;
    }}

    .news-item {{
        padding: 24px 0;
        border-bottom: 1px solid {c['border']};
        margin-bottom: 8px;
    }}
    
    .news-title-link {{
        text-decoration: none !important;
        color: {c['text']} !important;
        transition: opacity 0.2s ease;
    }}
    .news-title-link:hover {{ opacity: 0.7; }}
    
    .news-title {{
        font-size: 1.35rem; font-weight: 700; line-height: 1.4; margin-bottom: 12px; color: {c['text']};
    }}
    
    .news-excerpt {{
        font-size: 0.95rem; color: {c['sub_text']} !important; line-height: 1.6; margin-bottom: 16px;
        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
    }}
    
    .news-meta {{
        font-size: 0.85rem; color: {c['sub_text']} !important; font-weight: 500; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 12px;
    }}
    
    img.news-thumb {{
        width: 100%; aspect-ratio: 16/9; object-fit: cover;
        border-radius: 12px;
        margin-bottom: 16px;
        background-color: {c['border']};
    }}
    
    .stButton > button {{
        background-color: {c['button_bg']} !important;
        color: {c['button_text']} !important;
        border: 1px solid {c['border']} !important;
        border-radius: 980px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        font-size: 0.9rem !important;
    }}
    .stButton > button:hover, .stButton > button:hover p {{ 
        background-color: {c['accent']} !important; 
        color: {c['bg']} !important; 
    }}

    .stTabs [data-baseweb="tab-list"] {{ gap: 40px; border-bottom: 1px solid {c['border']}; }}
    .stTabs [data-baseweb="tab"] {{ height: 60px; font-size: 1.2rem; color: {c['sub_text']}; font-weight: 700; }}
    .stTabs [aria-selected="true"] {{ color: {c['text']} !important; border-bottom-color: {c['text']} !important; }}
    
    .score-badge {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-left: 8px;
        display: inline-block;
    }}
</style>
""", unsafe_allow_html=True)

# --- Login / Main Logic Switch ---

if 'guest_mode' not in st.session_state:
    st.session_state.guest_mode = False
if 'auth_step' not in st.session_state:
    st.session_state.auth_step = 'login' # login, 2fa, recovery_code, recovery_pass

# Helper to reset all settings to defaults
def reset_to_defaults():
    st.session_state.theme = 'Dark'
    st.session_state.bookmarks = []
    st.session_state.recommendation_keywords = []
    st.session_state.mute_words = []

# Helper to clear temporary auth flow state
def clear_auth_flow():
    st.session_state.auth_step = 'login'
    st.session_state.temp_email = None
    st.session_state.temp_secret = None

# Full logout helper
def logout():
    # Remove from DB if token exists
    token = st.context.cookies.get('session_token')
    if token:
        db.delete_persistent_session(token)
    
    st.session_state.user = None
    st.session_state.guest_mode = False
    clear_auth_flow()
    reset_to_defaults()
    # Clear browser cookie
    delete_cookie_js('session_token')

if not st.session_state.user and not st.session_state.guest_mode:
    # --- Login/Register/Recovery UI ---
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {c['bg']}; }}
        h1, h2, h3, label {{ color: {c['text']} !important; }}
        .stTextInput input {{ background-color: {c['input_bg']} !important; color: {c['text']} !important; }}
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"<h1 style='text-align: center;'>🍌 AI News Pro</h1>", unsafe_allow_html=True)
        
        # 2FA Verification Screen
        if st.session_state.auth_step == '2fa':
            st.markdown("### 2段階認証")
            st.info(f"認証コードを登録メールアドレスに送信しました。受信トレイを確認してください。")
            code_input = st.text_input("認証コード", key="2fa_code")
            if st.button("認証", use_container_width=True, type="primary"):
                if db.verify_2fa(st.session_state.temp_email, code_input):
                    email = st.session_state.temp_email
                    st.session_state.user = email
                    # Create persistent session
                    ip = get_remote_ip()
                    token = db.create_persistent_session(email, ip)
                    set_cookie_js('session_token', token)
                    
                    load_user_session() # Load settings for the new user
                    clear_auth_flow()   # Clear intermediate auth state
                    st.rerun()
                else:
                    st.error("コードが間違っています")
            if st.button("戻る", use_container_width=True):
                clear_auth_flow()
                st.rerun()

        # Recovery Code Screen
        elif st.session_state.auth_step == 'recovery_code':
            st.markdown("### パスワード再設定")
            st.info("認証コードをメールに送信しました。受信トレイを確認してください。")
            rec_code = st.text_input("認証コード", key="rec_code_input")
            if st.button("次へ", use_container_width=True, type="primary"):
                if db.verify_recovery_code(st.session_state.temp_email, rec_code):
                    st.session_state.auth_step = 'recovery_pass'
                    st.rerun()
                else:
                    st.error("コードが間違っています")
            if st.button("戻る"):
                clear_auth_state()
                st.rerun()

        # Recovery New Password Screen
        elif st.session_state.auth_step == 'recovery_pass':
            st.markdown("### 新しいパスワード")
            new_p1 = st.text_input("新しいパスワード", type="password", key="new_p1")
            new_p2 = st.text_input("確認用", type="password", key="new_p2")
            if st.button("変更", use_container_width=True, type="primary"):
                if new_p1 and new_p1 == new_p2:
                    db.update_password(st.session_state.temp_email, new_p1)
                    st.success("パスワードを変更しました！ログインしてください。")
                    clear_auth_state()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("パスワードが一致しません")

        # Main Auth Tabs (Login / Register / Forgot)
        else:
            tab_login, tab_register, tab_forgot = st.tabs(["ログイン", "新規登録", "パスワード忘れ"])
            
            with tab_login:
                l_mail = st.text_input("メールアドレス", key="l_mail")
                l_pass = st.text_input("パスワード", type="password", key="l_pass")
                if st.button("ログイン", use_container_width=True, type="primary"):
                    secret = db.verify_user(l_mail, l_pass)
                    if secret:
                        # Generate and send real code
                        code = db.set_auth_code(l_mail)
                        if send_auth_email(l_mail, "【AI News Pro】認証コード", f"あなたの認証コードは {code} です。"):
                            st.session_state.temp_email = l_mail
                            st.session_state.temp_secret = secret
                            st.session_state.auth_step = '2fa'
                            st.rerun()
                        else:
                            st.error("メール送信に失敗しました")
                    else:
                        st.error("メールアドレスまたはパスワードが間違っています")
            
            with tab_register:
                r_mail = st.text_input("メールアドレス", key="r_mail")
                r_pass = st.text_input("パスワード", type="password", key="r_pass")
                if st.button("アカウント作成", use_container_width=True):
                    if r_mail and r_pass:
                        secret = db.create_user(r_mail, r_pass)
                        if secret:
                            # Generate and send code
                            code = db.set_auth_code(r_mail)
                            if send_auth_email(r_mail, "【AI News Pro】新規登録 認証コード", f"新規登録を完了するための認証コードは {code} です。"):
                                st.session_state.temp_email = r_mail
                                st.session_state.temp_secret = secret
                                st.session_state.auth_step = '2fa'
                                st.success("認証コードを送信しました！")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("メール送信に失敗しました")
                        else:
                            st.error("そのメールアドレスは既に使用されています")
                    else:
                        st.warning("全ての項目を入力してください")

            with tab_forgot:
                f_mail = st.text_input("登録メールアドレス", key="f_mail")
                if st.button("コード送信", use_container_width=True):
                    if f_mail:
                        code = db.set_recovery_code(f_mail)
                        if code:
                            if send_auth_email(f_mail, "【AI News Pro】パスワード再設定コード", f"パスワード再設定用の認証コードは {code} です。"):
                                st.session_state.temp_email = f_mail
                                st.session_state.auth_step = 'recovery_code'
                                st.rerun()
                            else:
                                st.error("メール送信に失敗しました")
                        else:
                            st.error("ユーザーが見つかりません")
            
            st.divider()
            if st.button("ログインせずに利用する（ゲストモード）", use_container_width=True):
                st.session_state.guest_mode = True
                st.session_state.user = None
                st.rerun()
    
    st.stop() # Stop execution here if not logged in


# --- Main Content ---
st.markdown(f"<h1>{source}</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='color:{c['sub_text']}; font-size:1.3rem; font-weight:600; margin-top:-15px;'>{cat_label}</p>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["最新ニュース", "おすすめ", "保存済み", "検索"])

with tab1:
    content_col = st.container()
    with content_col:
        c1, c2 = st.columns([1, 1])
        with c1: 
            if st.button("更新", use_container_width=True): st.rerun()
        with c2:
            if st.button("🖼️ 全画像を読み込む", use_container_width=True):
                items = fetch_news(source, cat_code, "")
                for it in items:
                    ik = f"ic_{it['id']}"
                    if not it['img_src'] and ik not in st.session_state:
                        st.session_state[ik] = fetch_og_image(it['link'])
                st.rerun()

        with st.spinner("取得中..."):
            news_items = fetch_news(source, cat_code, "")
            
        if not news_items:
             st.info("ニュースが見つかりませんでした。")
        else:
             # 1. Filter Mute Words
             filtered_items = filter_muted_articles(news_items, st.session_state.mute_words)
             
             if not filtered_items:
                 st.info("すべての記事がミュートされました。")
             else:
                 # 2. Smart Grouping
                 grouped_items = group_articles(filtered_items)
                 
                 st.markdown(f"**表示中: {len(filtered_items)} 件 (グルーピング済)**")
                 
                 cols = st.columns(3)
                 for i, group in enumerate(grouped_items):
                     # Show the first article as main
                     main_item = group[0]
                     related_count = len(group) - 1
                     
                     with cols[i % 3]:
                         st.markdown(f'<div class="news-item">', unsafe_allow_html=True)
                         ik = f"ic_{main_item['id']}"
                         img = main_item['img_src'] or st.session_state.get(ik)
                         
                         st.markdown(f'<div class="news-meta">{main_item["source"]} • {main_item["published"]}</div>', unsafe_allow_html=True)
                         if img: st.markdown(f'<a href="{main_item["link"]}" target="_blank"><img src="{img}" class="news-thumb"></a>', unsafe_allow_html=True)
                         st.markdown(f'<a href="{main_item["link"]}" target="_blank" class="news-title-link"><div class="news-title">{main_item["title"]}</div></a>', unsafe_allow_html=True)
                         
                         if main_item['summary']:
                             st.markdown(f'<div class="news-excerpt">{main_item["summary"]}</div>', unsafe_allow_html=True)
                         
                         b1, b2 = st.columns(2)
                         with b1:
                              if not img:
                                 if st.button("🖼️ 画像", key=f"img_{i}", use_container_width=True):
                                     st.session_state[ik] = fetch_og_image(main_item['link'])
                                     st.rerun()
                         with b2:
                             if st.button("保存 🔖", key=f"sav_{i}", use_container_width=True):
                                 existing = [b for b in st.session_state.bookmarks if b['link'] == main_item['link']]
                                 if existing:
                                     st.session_state.bookmarks = [b for b in st.session_state.bookmarks if b['link'] != main_item['link']]
                                     st.toast("保存を解除しました")
                                 else:
                                     st.session_state.bookmarks.append(main_item)
                                     st.toast("保存しました")
                                 # Save Bookmark to DB
                                 if st.session_state.user:
                                     db.save_user_data(st.session_state.user, 'bookmarks', st.session_state.bookmarks)
                                 st.rerun()
                         
                         # Show Related Articles if any
                         if related_count > 0:
                             with st.expander(f"他 {related_count} 件の関連記事"):
                                 for rel in group[1:]:
                                     st.markdown(f"- [{rel['source']}] [{rel['title']}]({rel['link']})")
                         
                         st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    if not st.session_state.recommendation_keywords:
        st.info("サイドバーの「おすすめ設定」からキーワードを登録してください。")
    else:
        st.markdown(f"**登録キーワード:** {', '.join(st.session_state.recommendation_keywords)}")
        
        # Sorting options
        sort_option = st.radio("並び順", ["スコア順", "新しい順", "ソース別"], horizontal=True, key="rec_sort")
        
        with st.spinner("全ソースからおすすめ記事を取得中..."):
            scored_items = get_recommended_articles(st.session_state.recommendation_keywords)
            
            # Filter Mute Words
            if scored_items and st.session_state.mute_words:
                filtered_scored = []
                for score, item in scored_items:
                    text_check = (item['title'] + " " + item['summary']).lower()
                    if not any(mw.lower() in text_check for mw in st.session_state.mute_words):
                        filtered_scored.append((score, item))
                scored_items = filtered_scored
        
        if scored_items:
            # Apply sorting
            if sort_option == "新しい順":
                scored_items.sort(key=lambda x: x[1]['published'], reverse=True)
            elif sort_option == "ソース別":
                scored_items.sort(key=lambda x: x[1]['source'])
            # Default is already score order
            
            # Bulk image load button
            if st.button("🖼️ 全画像を読み込む", key="rec_load_all_images", use_container_width=True):
                for score, item in scored_items:
                    ik = f"ic_{item['id']}"
                    if not item['img_src'] and ik not in st.session_state:
                        st.session_state[ik] = fetch_og_image(item['link'])
                st.rerun()
            
            cols = st.columns(3)
            for i, (score, item) in enumerate(scored_items):
                with cols[i % 3]:
                    st.markdown(f'<div class="news-item">', unsafe_allow_html=True)
                    ik = f"ic_{item['id']}"
                    img = item['img_src'] or st.session_state.get(ik)
                    
                    # Display source and score
                    st.markdown(
                        f'<div class="news-meta">{item["source"]} • {item["published"]}'
                        f'<span class="score-badge">🏆 {score}点</span></div>', 
                        unsafe_allow_html=True
                    )
                    if img: st.markdown(f'<a href="{item["link"]}" target="_blank"><img src="{img}" class="news-thumb"></a>', unsafe_allow_html=True)
                    st.markdown(f'<a href="{item["link"]}" target="_blank" class="news-title-link"><div class="news-title">{item["title"]}</div></a>', unsafe_allow_html=True)
                    
                    if item['summary']:
                        st.markdown(f'<div class="news-excerpt">{item["summary"]}</div>', unsafe_allow_html=True)
                    
                    if st.button("保存 🔖", key=f"rec_sav_{i}", use_container_width=True):
                        if not any(b['link'] == item['link'] for b in st.session_state.bookmarks):
                            st.session_state.bookmarks.append(item)
                            st.toast("保存しました")
                            # Save to DB
                            if st.session_state.user:
                                db.save_user_data(st.session_state.user, 'bookmarks', st.session_state.bookmarks)
                        else:
                            st.toast("既に保存されています")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("キーワードに一致する記事が見つかりませんでした。")

with tab3:
    if not st.session_state.bookmarks:
        st.info("保存された記事はありません。")
    else:
        # CSV Export button
        if st.button("📥 CSVでエクスポート", use_container_width=True):
            df = pd.DataFrame([{
                'タイトル': b['title'],
                'URL': b['link'],
                'ソース': b['source'],
                '日付': b['published'],
                '要約': b['summary']
            } for b in st.session_state.bookmarks])
            
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="⬇️ ダウンロード",
                data=csv,
                file_name="bookmarks.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        st.divider()
        
        cols_b = st.columns(3)
        for i, item in enumerate(st.session_state.bookmarks):
            with cols_b[i % 3]:
                st.markdown(f'<div class="news-item">', unsafe_allow_html=True)
                ik = f"ic_{item['id']}"
                img = item.get('img_src') or st.session_state.get(ik)
                
                st.markdown(f'<div class="news-meta">{item["source"]} • {item["published"]}</div>', unsafe_allow_html=True)
                if img: st.markdown(f'<a href="{item["link"]}" target="_blank"><img src="{img}" class="news-thumb"></a>', unsafe_allow_html=True)
                st.markdown(f'<a href="{item["link"]}" target="_blank" class="news-title-link"><div class="news-title">{item["title"]}</div></a>', unsafe_allow_html=True)
                
                if item['summary']:
                    st.markdown(f'<div class="news-excerpt">{item["summary"]}</div>', unsafe_allow_html=True)
                
                if st.button("削除 🗑️", key=f"del_{i}", use_container_width=True):
                    st.session_state.bookmarks.pop(i)
                    # Save to DB
                    if st.session_state.user:
                        db.save_user_data(st.session_state.user, 'bookmarks', st.session_state.bookmarks)
                    st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.markdown("### 全ソース横断検索 🔍")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("検索ワードを入力", placeholder="例: 生成AI, 半導体, 選挙", key="global_search_input")
    with col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        search_btn = st.button("検索", use_container_width=True, type="primary")
        
    if search_query:
        with st.spinner(f"'{search_query}' で全ソースを検索中..."):
            results = get_search_results(search_query)
            
            filtered_results = results

            # Filter Mute Words
            search_final = filter_muted_articles(filtered_results, st.session_state.mute_words)
            
            st.markdown(f"**検索結果: {len(search_final)} 件**")
            
            if not search_final:
                st.info("該当する記事が見つかりませんでした（またはミュートされました）。")
            else:
                # Grouping
                search_grouped = group_articles(search_final)
                st.caption(f"(グルーピング済)")
                
                cols = st.columns(3)
                for i, group in enumerate(search_grouped):
                    main_item = group[0]
                    related_count = len(group) - 1
                    
                    with cols[i % 3]:
                        st.markdown(f'<div class="news-item">', unsafe_allow_html=True)
                        ik = f"sic_{i}_{main_item['link']}" # unique key
                        img = main_item.get('img_src') or st.session_state.get(ik)
                        
                        st.markdown(f'<div class="news-meta">{main_item["source"]} • {main_item["published"]}</div>', unsafe_allow_html=True)
                        if img: st.markdown(f'<a href="{main_item["link"]}" target="_blank"><img src="{img}" class="news-thumb"></a>', unsafe_allow_html=True)
                        st.markdown(f'<a href="{main_item["link"]}" target="_blank" class="news-title-link"><div class="news-title">{main_item["title"]}</div></a>', unsafe_allow_html=True)
                        
                        if main_item['summary']:
                            st.markdown(f'<div class="news-excerpt">{main_item["summary"]}</div>', unsafe_allow_html=True)
                        
                        b1, b2 = st.columns(2)
                        with b1:
                            if not img:
                                if st.button("🖼️ 画像", key=f"s_img_{i}", use_container_width=True):
                                    st.session_state[ik] = fetch_og_image(main_item['link'])
                                    st.rerun()
                        with b2:
                            if st.button("保存 🔖", key=f"s_sav_{i}", use_container_width=True):
                                # Save logic
                                existing = [b for b in st.session_state.bookmarks if b['link'] == main_item['link']]
                                if existing:
                                    st.session_state.bookmarks = [b for b in st.session_state.bookmarks if b['link'] != main_item['link']]
                                    st.toast("保存を解除しました")
                                else:
                                    st.session_state.bookmarks.append(main_item)
                                    st.toast("保存しました")
                                
                                if st.session_state.user:
                                    db.save_user_data(st.session_state.user, 'bookmarks', st.session_state.bookmarks)
                                st.rerun()
                        
                        # Show Related Search Results
                        if related_count > 0:
                            with st.expander(f"他 {related_count} 件"):
                                for rel in group[1:]:
                                    st.markdown(f"- [{rel['source']}] [{rel['title']}]({rel['link']})")

                        st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown(f'<a href="{item["link"]}" target="_blank" class="news-title-link"><div class="news-title">{item["title"]}</div></a>', unsafe_allow_html=True)
                        
                        if item['summary']:
                            st.markdown(f'<div class="news-excerpt">{item["summary"]}</div>', unsafe_allow_html=True)
                            
                        if st.button("保存 🔖", key=f"search_sav_{i}", use_container_width=True):
                            if not any(b['link'] == item['link'] for b in st.session_state.bookmarks):
                                st.session_state.bookmarks.append(item)
                                st.toast("保存しました")
                                # Save to DB
                                if st.session_state.user:
                                    db.save_user_data(st.session_state.user, 'bookmarks', st.session_state.bookmarks)
                        
                
                st.markdown('</div>', unsafe_allow_html=True)
