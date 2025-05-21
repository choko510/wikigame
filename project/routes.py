from flask import request, render_template, jsonify, session
from . import app # Import the app instance
from .utils import is_safe_url, get_random_wikipedia_page, extract_wiki_links # Import your utils
from .models import rooms, kks, ALLOWED_DOMAIN # Import models
from bs4 import BeautifulSoup # For proxy
import requests # For proxy
import html # For proxy
from urllib.parse import urlparse, unquote # For proxy and check_target
import re # For proxy

@app.route('/')
def index():
    """新しいトップページ"""
    return render_template('index.html')

@app.route('/wikipedia_game') # シングルプレイヤーゲームの新しいルート
def wikipedia_game():
    """シングルプレイヤー Wikipedia ゲームページ"""
    return render_template('wikipedia_game.html')

@app.route('/api/check-target')
def check_target():
    """目標ページに到達したかチェック"""
    current_url = request.args.get('current')
    target_url = request.args.get('target', 'https://ja.wikipedia.org/wiki/日本')

    if not is_safe_url(current_url) or not is_safe_url(target_url):
        return jsonify({'error': '無効なURLです。WikipediaのURLを指定してください。'}), 400
    
    current_path = unquote(urlparse(current_url).path)
    target_path = unquote(urlparse(target_url).path)
    
    is_target = current_path.lower() == target_path.lower()
    
    print(f"比較: {current_path} vs {target_path} = {is_target}")
    
    title = ""
    try:
        response = requests.get(current_url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else ""
    except requests.exceptions.RequestException as e:
        print(f"Error fetching title for {current_url}: {e}")
    except Exception as e:
        print(f"Generic error fetching title for {current_url}: {e}")

    return jsonify({
        'is_target': is_target,
        'current_path': current_path,
        'target_path': target_path,
        'title': title
    })

@app.route('/api/random-page')
def random_page():
    """ランダムなWikipediaページを取得"""
    url = get_random_wikipedia_page()
    return jsonify({'url': url})

@app.route('/api/page-links')
def page_links():
    """指定されたページのリンクを取得"""
    url = request.args.get('url')
    if not is_safe_url(url):
        return jsonify({'error': '無効なURLです。WikipediaのURLを指定してください。'}), 400
    links = extract_wiki_links(url)
    return jsonify({'links': links})

@app.route('/proxy')
def proxy():
    """ウェブページをプロキシ"""
    url = request.args.get('url')
    game_mode = request.args.get('mode', 'navigation')
    room_id = request.args.get('room_id', '')
    
    if not is_safe_url(url):
        return "無効なURLです。WikipediaのURLを指定してください。", 400
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        content = response.text
        
        # Base URL for resolving relative links, specific to ja.wikipedia.org for now
        # This might need to be more dynamic if other language wikis are used.
        base_url_for_links = "https://ja.wikipedia.org"

        content = content.replace('href="/w/', f'href="{base_url_for_links}/w/')
        content = content.replace('href="/static/', f'href="{base_url_for_links}/static/')
        
        soup = BeautifulSoup(content, 'html.parser')

        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        for tag in soup.find_all(True):
            attrs_to_remove = []
            for attr_name, attr_value in tag.attrs.items():
                if attr_name.lower().startswith('on'):
                    attrs_to_remove.append(attr_name)
                elif attr_name.lower() in ['href', 'src', 'action', 'formaction'] and \
                     isinstance(attr_value, str) and attr_value.lower().startswith('javascript:'):
                    attrs_to_remove.append(attr_name)
            for attr_name in attrs_to_remove:
                del tag[attr_name]
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('/wiki/'):
                a_tag['href'] = f"{base_url_for_links}{href}"
            # Leave '#' links as they are for in-page navigation
            # External links are not modified here, but client-side JS should handle them
        
        content = str(soup)
        soup_for_removal = BeautifulSoup(content, 'html.parser')

        # Remove problematic elements
        elements_to_remove_selectors = [
            'div.vector-header-container',
            'div.mw-footer-container',
            'div#p-lang-btn',
            'div.vector-page-toolbar',
            'div.mw-editsection',
            # Add other selectors if needed
        ]
        for selector in elements_to_remove_selectors:
            for el in soup_for_removal.select(selector):
                el.decompose()

        if game_mode == 'guessing':
            title_element = soup_for_removal.select_one("h1#firstHeading span.mw-page-title-main") # More specific selector
            if not title_element: # Fallback for different structures perhaps
                 title_element = soup_for_removal.select_one("body > div > div > div:nth-child(3) > main > header > h1 > span")

            if title_element:
                original_text = title_element.get_text(strip=True)
                replaced_text = "X" * len(original_text)
                title_element.string = replaced_text
                
                # Prepare for text replacement throughout the document
                # This part needs kks from .models
                kks_result = kks.convert(original_text)
                hiratext = ''.join([item['hira'] for item in kks_result])
                replaced_hiratext = "X" * len(hiratext)
                # Romaji conversion might be too broad and replace parts of words unintentionally.
                # Consider if romaji replacement is truly needed or if title and hiragana are enough.
                
                modified_html = str(soup_for_removal)
                # Order of replacement matters if titles can contain hiragana versions of other titles
                modified_html = modified_html.replace(original_text, replaced_text)
                if hiratext != original_text: # Avoid double replacement if original is already hiragana
                    modified_html = modified_html.replace(hiratext, replaced_hiratext)
                
                if room_id and room_id in rooms:
                    if 'current_pages' not in rooms[room_id]:
                        rooms[room_id]['current_pages'] = {}
                    page_path = urlparse(url).path
                    page_title_for_storage = unquote(page_path.split('/')[-1]).replace('_', ' ')
                    rooms[room_id]['current_pages'][url] = page_title_for_storage
                
                return modified_html
        
        modified_html = str(soup_for_removal)
        return modified_html
    except requests.exceptions.RequestException as e:
        return f"プロキシリクエストエラー: {e}", 500
    except Exception as e:
        return f"プロキシ一般エラー: {e}", 500

@app.route('/multiplayer')
def multiplayer():
    """マルチプレイヤーゲームページ"""
    return render_template('multiplayer.html')
