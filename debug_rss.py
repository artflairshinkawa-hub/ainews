import feedparser
import pprint

# Bing News Headlines (Query: Top News)
url = "https://www.bing.com/news/search?q=%E3%83%88%E3%83%83%E3%83%97%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9&format=rss&cc=JP"
feed = feedparser.parse(url)

print(f"Total entries: {len(feed.entries)}")

if feed.entries:
    entry = feed.entries[0]
    print("\n--- Keys ---")
    pprint.pprint(list(entry.keys()))
    
    print("\n--- Image URLs ---")
    if 'news_image' in entry:
        print(f"news_image: {entry.news_image}")
        
    if 'media_content' in entry:
        print(f"media_content: {entry.media_content}")
        
    if 'media_thumbnail' in entry:
        print(f"media_thumbnail: {entry.media_thumbnail}")


