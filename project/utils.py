import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
# Removed unused 're' and 'unquote' for now. Will add back if other utils need them.

from .models import ALLOWED_DOMAIN

def is_safe_url(url):
    """指定されたURLが安全なWikipediaのURLか検証する"""
    if not url:
        return False
    try:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            return False
        # Ensure ALLOWED_DOMAIN is correctly referenced
        if parsed_url.hostname and \
           (parsed_url.hostname == ALLOWED_DOMAIN or parsed_url.hostname.endswith('.' + ALLOWED_DOMAIN)):
            return True
    except Exception:
        return False
    return False

def get_random_wikipedia_page(language='ja'):
    """ランダムなWikipediaページのURLを取得"""
    base_url = f'https://{language}.wikipedia.org/wiki/特別:おまかせ表示'
    # It's good practice to handle potential request errors
    try:
        response = requests.get(base_url, allow_redirects=True, timeout=5)
        response.raise_for_status() # Raise an exception for HTTP errors
        return response.url
    except requests.exceptions.RequestException as e:
        print(f"Error fetching random Wikipedia page: {e}")
        # Fallback or error handling - for now, returning a default or raising
        return f'https://{language}.wikipedia.org/wiki/メインページ' # Fallback to main page

def extract_wiki_links(url):
    """指定されたWikipediaページのリンクを抽出"""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        # Specify a parser to avoid warnings and ensure consistency
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        # Ensure a_tag['href'] exists before trying to process it
        for a_tag in soup.select('#mw-content-text a[href]'):
            href = a_tag['href']
            
            if href.startswith('/wiki/'):
                # Avoid constructing URLs with fragments that look like full URLs
                if not href.startswith('/wiki/Special:') and \
                   not href.startswith('/wiki/File:') and \
                   not href.startswith('/wiki/Help:') and \
                   not href.startswith('/wiki/Category:') and \
                   not href.startswith('/wiki/Template:') and \
                   not href.startswith('/wiki/Portal:') and \
                   not href.startswith('/wiki/Wikipedia:') and \
                   not href.startswith('/wiki/ノート:') and \
                   ':' not in href.split('/wiki/')[-1]: # More robust check for namespace in path component
                    full_url = f"https://ja.wikipedia.org{href}"
                    links.append(full_url)
            # Consider if absolute Wikipedia links should also be processed/validated here
            # For now, sticking to relative /wiki/ links as per original logic
            
        return list(set(links)) # Remove duplicates
    except requests.exceptions.RequestException as e:
        print(f"リンク抽出エラー (RequestException) for {url}: {e}")
        return []
    except Exception as e:
        print(f"リンク抽出エラー (General Exception) for {url}: {e}")
        return []
