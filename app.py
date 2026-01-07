import streamlit as st
import feedparser
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import requests
import re
from urllib.parse import quote

# Page Config
st.set_page_config(page_title="AIニュース Pro", page_icon="🤍", layout="wide")

# --- Session State ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'Dark'
if 'bookmarks' not in st.session_state:
    st.session_state.bookmarks = []
if 'recommendation_keywords' not in st.session_state:
    st.session_state.recommendation_keywords = []
if 'date_filter' not in st.session_state:
    st.session_state.date_filter = "すべて"

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

@st.cache_data(ttl=300)
def fetch_news(source, category_code, query_text):
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
        q = query_text if category_code != "HEADLINES" else "Top+Stories"
        url = f"https://www.bing.com/news/search?q={quote(q)}&format=rss&cc=JP"
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
            processed.append({
                'title': title, 'link': link, 'summary': summary_text, 
                'img_src': get_high_res_image_url(img), 'source': source, 
                'id': link, 'published': entry.get('published', '')[:16]
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

def get_recommended_articles(keywords, max_articles=30):
    """Aggregate articles from all sources and score them."""
    if not keywords:
        return []
    
    all_sources = [
        "ナタリー", "Yahoo! ニュース", "ライブドアニュース", "NHK ニュース", 
        "Google News", "Bing News", "Gigazine", "ITmedia", 
        "CNET Japan", "TechCrunch Japan", "Qiita", "Zenn"
    ]
    all_articles = []
    
    # Collect articles from all sources
    for source in all_sources:
        try:
            articles = fetch_news(source, "HEADLINES", "")
            for article in articles:
                article['source'] = source
            all_articles.extend(articles)
        except:
            continue
    
    # Score and filter articles
    scored_articles = []
    seen_titles = set()
    
    for article in all_articles:
        # Deduplicate by title
        if article['title'] in seen_titles:
            continue
        seen_titles.add(article['title'])
        
        score = calculate_article_score(article, keywords)
        if score > 0:
            scored_articles.append((score, article))
    
    # Sort by score and return top articles with scores
    scored_articles.sort(reverse=True, key=lambda x: x[0])
    return scored_articles[:max_articles]


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
    
    .sidebar-logo {{
        display: flex; align-items: center; gap: 14px;
        padding-bottom: 24px; margin-bottom: 32px;
        border-bottom: 1px solid {c['border']};
    }}
    .logo-text {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.05em; color: {c['text']}; }}

    [data-testid="stSidebar"] section[data-testid="stSidebarNav"] span,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] div {{
        color: {c['text']} !important;
        font-weight: 600 !important;
    }}

    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
        background-color: {c['input_bg']} !important;
        border: 1px solid {c['border']} !important;
        border-radius: 8px !important;
    }}
    div[data-baseweb="select"] span, div[data-baseweb="input"] input,
    div[data-baseweb="select"] div[aria-selected="true"] {{
        color: {c['text']} !important;
        -webkit-text-fill-color: {c['text']} !important;
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
    .stButton > button:hover {{ background-color: {c['accent']} !important; color: {c['bg']} !important; }}

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

# --- Sidebar ---
with st.sidebar:
    st.markdown(f"""
        <div class="sidebar-logo">
            <svg viewBox="0 0 24 24" width="35" height="35" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="{c['text']}"/>
            </svg>
            <span class="logo-text">AI News Pro</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### Settings")
    theme_btn = st.radio("テーマ選択", ["Dark", "Light"], horizontal=True, index=0 if st.session_state.theme == "Dark" else 1)
    if theme_btn != st.session_state.theme:
        st.session_state.theme = theme_btn
        st.rerun()

    source = st.selectbox(
        "ニュースソース", 
        ["ナタリー", "Yahoo! ニュース", "ライブドアニュース", "NHK ニュース", 
         "Google News", "Bing News", "Gigazine", "ITmedia", 
         "CNET Japan", "TechCrunch Japan", "Qiita", "Zenn"], 
        index=2, 
        key="news_source_select"
    )
    
    if source == "Yahoo! ニュース":
        cats = {
            "主要": "HEADLINES", "IT・科学": "TECHNOLOGY", "経済": "BUSINESS", "国際": "International", 
            "エンタメ": "Entertainment", "スポーツ": "Sports", "国内": "Domestic", "ライフ": "Life", 
            "地域": "Local", "キーワード検索": "SEARCH"
        }
    elif source == "NHK ニュース":
        cats = {
            "主要": "HEADLINES", "社会": "Social", "政治": "Politics", "国際": "International", 
            "経済": "Economy", "科学・文化": "Science", "スポーツ": "Sports", "地域": "Local",
            "キーワード検索": "SEARCH"
        }
    elif source == "Google News":
        cats = {
            "トップ": "HEADLINES", "テクノロジー": "TECHNOLOGY", "ビジネス": "BUSINESS", "国際": "International", 
            "エンタメ": "Entertainment", "スポーツ": "Sports", "科学": "Science", "健康": "Health", "キーワード検索": "SEARCH"
        }
    elif source == "ITmedia":
        cats = {
            "総合": "ALL", "モバイル": "MOBILE", "エンタープライズ": "ENTERPRISE", 
            "PC USER": "PCUSER", "ビジネスオンライン": "BUSINESS", "キーワード検索": "SEARCH"
        }
    elif source in ["Qiita", "Zenn"]:
        cats = {"トレンド": "HEADLINES", "タグ/トピック検索": "SEARCH"}
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
            "健康": "Health", "スポーツ": "Sports", "国際": "World", "国内": "Japan",
            "キーワード検索": "SEARCH"
        }
        
    cat_label = st.selectbox("カテゴリー", list(cats.keys()), key=f"cat_select_{source}")
    cat_code = cats[cat_label]
    query = st.text_input("検索ワード", "AI", key=f"query_input_{source}") if cat_code == "SEARCH" else cat_label
    
    st.divider()
    
    # Date filter
    st.session_state.date_filter = st.selectbox(
        "表示期間", 
        ["すべて", "今日", "過去3日", "過去1週間"],
        index=["すべて", "今日", "過去3日", "過去1週間"].index(st.session_state.date_filter)
    )
    
    st.divider()
    st.markdown("### おすすめ設定")
    
    # Keyword management with Enter key support
    def add_keyword():
        new_kw = st.session_state.new_keyword_input
        if new_kw and new_kw not in st.session_state.recommendation_keywords:
            if len(st.session_state.recommendation_keywords) < 5:
                st.session_state.recommendation_keywords.append(new_kw)
                st.session_state.new_keyword_input = ""  # Clear input
    
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
                    st.rerun()
    
    st.divider()
    auto_ref = st.toggle("自動更新 (10分)")
    if auto_ref: st.markdown('<meta http-equiv="refresh" content="600">', unsafe_allow_html=True)

# --- Main Content ---
st.markdown(f"<h1>{source}</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='color:{c['sub_text']}; font-size:1.3rem; font-weight:600; margin-top:-15px;'>{cat_label}</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["最新ニュース", "おすすめ", "保存済み"])

with tab1:
    content_col = st.container()
    with content_col:
        c1, c2 = st.columns([1, 1])
        with c1: 
            if st.button("更新", use_container_width=True): st.rerun()
        with c2:
            if st.button("🖼️ 全画像を読み込む", use_container_width=True):
                items = fetch_news(source, cat_code, query)
                for it in items:
                    ik = f"ic_{it['id']}"
                    if not it['img_src'] and ik not in st.session_state:
                        st.session_state[ik] = fetch_og_image(it['link'])
                st.rerun()

        with st.spinner("取得中..."):
            news_items = fetch_news(source, cat_code, query)
            
        if news_items:
            cols = st.columns(3)
            for i, item in enumerate(news_items):
                with cols[i % 3]:
                    st.markdown(f'<div class="news-item">', unsafe_allow_html=True)
                    ik = f"ic_{item['id']}"
                    img = item['img_src'] or st.session_state.get(ik)
                    
                    st.markdown(f'<div class="news-meta">{item["source"]} • {item["published"]}</div>', unsafe_allow_html=True)
                    if img: st.markdown(f'<a href="{item["link"]}" target="_blank"><img src="{img}" class="news-thumb"></a>', unsafe_allow_html=True)
                    st.markdown(f'<a href="{item["link"]}" target="_blank" class="news-title-link"><div class="news-title">{item["title"]}</div></a>', unsafe_allow_html=True)
                    
                    if item['summary']:
                        st.markdown(f'<div class="news-excerpt">{item["summary"]}</div>', unsafe_allow_html=True)
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        if not img:
                            if st.button("🖼️ 画像", key=f"img_{i}", use_container_width=True):
                                st.session_state[ik] = fetch_og_image(item['link'])
                                st.rerun()
                    with b2:
                        if st.button("保存 🔖", key=f"sav_{i}", use_container_width=True):
                            if not any(b['link'] == item['link'] for b in st.session_state.bookmarks):
                                st.session_state.bookmarks.append(item)
                                st.toast("保存しました")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        else: st.info("ニュースが見つかりませんでした。")

with tab2:
    if not st.session_state.recommendation_keywords:
        st.info("サイドバーの「おすすめ設定」からキーワードを登録してください。")
    else:
        st.markdown(f"**登録キーワード:** {', '.join(st.session_state.recommendation_keywords)}")
        
        # Sorting options
        sort_option = st.radio("並び順", ["スコア順", "新しい順", "ソース別"], horizontal=True, key="rec_sort")
        
        with st.spinner("全ソースからおすすめ記事を取得中..."):
            scored_items = get_recommended_articles(st.session_state.recommendation_keywords)
        
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
                
                if st.button("削除 🗑️", key=f"rm_{i}", use_container_width=True):
                    st.session_state.bookmarks.pop(i)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
