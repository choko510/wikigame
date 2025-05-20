from flask import Flask, request, render_template, jsonify, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import requests
import random
import uuid
from bs4 import BeautifulSoup
from collections import defaultdict
import time
import html
import re
from urllib.parse import urlparse
from pykakasi import kakasi  # 日本語をローマ字に変換するライブラリ

# kakasiの初期化
kks = kakasi()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wiki-game-secret-key'  # セッション用の秘密鍵
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ゲームルーム管理
rooms = {}
# プレイヤー管理（player_id -> 部屋ID）
player_rooms = {}
# ゲーム状態管理
game_states = defaultdict(dict)

ALLOWED_DOMAIN = "wikipedia.org"

def is_safe_url(url):
    """指定されたURLが安全なWikipediaのURLか検証する"""
    if not url:
        return False
    try:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            return False
        if parsed_url.hostname and \
           (parsed_url.hostname == ALLOWED_DOMAIN or parsed_url.hostname.endswith('.' + ALLOWED_DOMAIN)):
            return True
    except Exception:
        return False
    return False

def get_random_wikipedia_page(language='ja'):
    """ランダムなWikipediaページのURLを取得"""
    base_url = f'https://{language}.wikipedia.org/wiki/特別:おまかせ表示'
    response = requests.get(base_url, allow_redirects=True)
    return response.url

def extract_wiki_links(url):
    """指定されたWikipediaページのリンクを抽出"""
    try:
        response = requests.get(url)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # メインコンテンツ内のWikipediaリンクを抽出
        links = []
        for a in soup.select('#mw-content-text a'):
            href = a.get('href', '')
            
            # リンクを絶対URLに変換
            if href.startswith('/wiki/'):
                full_url = f'https://ja.wikipedia.org{href}'
                
                # 特殊ページを除外
                if ':' not in full_url:
                    links.append(full_url)
        
        return list(set(links))
    except Exception as e:
        print(f"リンク抽出エラー: {e}")
        return []

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
    
    # URLからパス部分を抽出してデコード
    from urllib.parse import urlparse, unquote
    current_path = unquote(urlparse(current_url).path)
    target_path = unquote(urlparse(target_url).path)
    
    # パスが一致するかチェック（大文字小文字を無視）
    is_target = current_path.lower() == target_path.lower()
    
    print(f"比較: {current_path} vs {target_path} = {is_target}")
    
    # タイトル取得（オプション）
    title = ""
    try:
        response = requests.get(current_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else ""
    except:
        pass
    
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
    game_mode = request.args.get('mode', 'navigation')  # デフォルトはナビゲーションモード
    room_id = request.args.get('room_id', '')  # ルームIDがあれば取得
    
    if not is_safe_url(url):
        return "無効なURLです。WikipediaのURLを指定してください。", 400
    try:
        response = requests.get(url)
        
        # HTMLを取得
        content = response.text
        
        # CSSリンクを絶対パスに変換
        content = content.replace('href="/w/', 'href="https://ja.wikipedia.org/w/')
        content = content.replace('href="/static/', 'href="https://ja.wikipedia.org/static/')
        
        # BeautifulSoupを使用してスクリプトや危険な属性を削除
        soup = BeautifulSoup(content, 'html.parser')

        # scriptタグとstyleタグを削除
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # イベントハンドラ属性とjavascript:リンクを削除
        for tag in soup.find_all(True): # すべてのタグを対象
            attrs_to_remove = []
            for attr_name, attr_value in tag.attrs.items():
                if attr_name.lower().startswith('on'): # on* イベントハンドラ
                    attrs_to_remove.append(attr_name)
                elif attr_name.lower() in ['href', 'src', 'action', 'formaction'] and \
                     isinstance(attr_value, str) and attr_value.lower().startswith('javascript:'): # javascript:プロトコル
                    attrs_to_remove.append(attr_name)
            for attr_name in attrs_to_remove:
                del tag[attr_name]
        
        # リンクを絶対パスに変換 (これは安全な操作なので残す)
        # ただし、soupオブジェクトに対して行う方がより堅牢
        for a_tag in soup.find_all('a', href=True):
            if a_tag['href'].startswith('/wiki/'):
                a_tag['href'] = f"https://ja.wikipedia.org{a_tag['href']}"
        
        content = str(soup) # 更新されたHTMLを取得

        # soupオブジェクトをコピーして既存の要素削除処理に使用
        soup_for_removal = BeautifulSoup(content, 'html.parser')
        # class属性が'vector-header-container'を持つdivタグを検索して削除
        for div in soup_for_removal.find_all('div', class_='vector-header-container'):
            div.decompose()

        for div in soup_for_removal.find_all('div', class_='mw-footer-container'):
            div.decompose()
        
        for div in soup_for_removal.find_all('div', id='p-lang-btn'):
            div.decompose()

        for div in soup_for_removal.find_all('div', class_='vector-page-toolbar'):
            div.decompose()

        for div in soup_for_removal.find_all('div', class_='mw-editsection'):
            div.decompose()

        # ゲームモードが「当てる」モードの場合、タイトルをXで置き換える
        if game_mode == 'guessing':
            # タイトル要素を取得（ページ名部分）
            element = soup_for_removal.select_one("body > div > div > div:nth-child(3) > main > header > h1 > span")
            
            if element:
                original_text = element.text  # 元の文字列を取得
                replaced_text = "X" * len(original_text)  # 元の文字列の長さ分のXに置き換え
                element.string = replaced_text  # 要素の内容を置き換え
                
                # 括弧付きタイトルの場合、括弧前の部分を抽出
                aresult = re.match(r"(.+?)_\(.+\)", original_text)
                if aresult:
                    extracted_text = aresult.group(1)
                    original_text = extracted_text
                
                # ひらがなとローマ字変換
                kksresult = kks.convert(original_text)
                hiratext = ''.join([item['hira'] for item in kksresult])
                replaced_hiratext = "X" * len(hiratext)
                romazitext = ' '.join([item['hepburn'] for item in kksresult])
                replaced_romazitext = "X" * len(romazitext)
                
                # ページ内の全てのテキストから元のタイトルを置換
                modified_html = str(soup_for_removal)
                modified_html = modified_html.replace(original_text, replaced_text)
                modified_html = modified_html.replace(hiratext, replaced_hiratext)
                modified_html = modified_html.replace(romazitext, replaced_romazitext)
                
                # ルームIDがある場合、ページタイトルを保存しておく（答え合わせ用）
                if room_id and room_id in rooms:
                    if 'current_pages' not in rooms[room_id]:
                        rooms[room_id]['current_pages'] = {}
                    # デコードして_を空白に置き換え
                    from urllib.parse import unquote
                    page_path = urlparse(url).path
                    page_title = unquote(page_path.split('/')[-1]).replace('_', ' ')
                    rooms[room_id]['current_pages'][url] = page_title
                
                return modified_html
        
        # 通常のナビゲーションモードではそのまま表示
        modified_html = str(soup_for_removal)
        return modified_html
    except Exception as e:
        return f"プロキシエラー: {e}", 500

# 新しいルートを追加
@app.route('/multiplayer')
def multiplayer():
    """マルチプレイヤーゲームページ"""
    return render_template('multiplayer.html')

# WebSocketイベントハンドラ
@socketio.on('connect')
def handle_connect():
    """クライアント接続時の処理"""
    player_id = request.sid
    emit('connection_response', {'status': 'connected', 'player_id': player_id})
    print(f"Player connected: {player_id}")

@socketio.on('disconnect')
def handle_disconnect():
    """クライアント切断時の処理"""
    player_id = request.sid
    # プレイヤーが部屋に参加していれば、部屋から削除
    if player_id in player_rooms:
        room_id = player_rooms[player_id]
        if room_id in rooms:
            # 部屋から退出
            leave_room(room_id)
            rooms[room_id]['players'].remove(player_id)
            
            # 部屋が空になったら削除
            if len(rooms[room_id]['players']) == 0:
                del rooms[room_id]
                if room_id in game_states:
                    del game_states[room_id]
            else:
                # 残りのプレイヤーに通知
                emit('player_left', {'player_id': player_id}, room=room_id)
        
        # プレイヤーの部屋情報を削除
        del player_rooms[player_id]
    
    print(f"Player disconnected: {player_id}")

@socketio.on('create_room')
def handle_create_room(data):
    """新しいゲームルームを作成"""
    player_id = request.sid
    raw_username = data.get('username', f'プレイヤー{random.randint(1000, 9999)}')
    username = html.escape(raw_username)
    
    # 新しいルームIDを生成
    room_id = str(uuid.uuid4())[:8]
    
    # ルーム情報を保存
    rooms[room_id] = {
        'id': room_id,
        'name': f"{username}の部屋", # usernameは既にエスケープ済み
        'host': player_id,
        'players': [player_id],
        'player_info': {player_id: {'username': username, 'ready': False}},
        'status': 'waiting',  # waiting, playing, finished
        'max_players': 4,
        'target_url': 'https://ja.wikipedia.org/wiki/日本',  # 初期デフォルト値
        'settings': {
            'allow_ctrl_f': True, # デフォルトでCtrl+Fを許可
            'game_mode': 'navigation'  # デフォルトはナビゲーションモード (navigation/guessing)
        }
    }
    
    # プレイヤーをルームに紐付け
    player_rooms[player_id] = room_id
    
    # ルームに参加
    join_room(room_id)
    
    emit('room_created', {
        'room_id': room_id,
        'room_info': rooms[room_id]
    })
    
    print(f"Room created: {room_id} by {username} ({player_id})")

@socketio.on('join_room')
def handle_join_room(data):
    """既存のゲームルームに参加"""
    player_id = request.sid
    room_id = data.get('room_id')
    raw_username = data.get('username', f'プレイヤー{random.randint(1000, 9999)}')
    username = html.escape(raw_username)
    
    if not room_id or room_id not in rooms:
        emit('error', {'message': '部屋が見つかりません'})
        return
    
    room = rooms[room_id]
    
    # 部屋が満員かゲーム中の場合は参加できない
    if len(room['players']) >= room['max_players']:
        emit('error', {'message': '部屋が満員です'})
        return
    
    if room['status'] != 'waiting':
        emit('error', {'message': 'ゲームはすでに始まっています'})
        return
    
    # プレイヤーを部屋に追加
    room['players'].append(player_id)
    room['player_info'][player_id] = {'username': username, 'ready': False}
    
    # プレイヤーをルームに紐付け
    player_rooms[player_id] = room_id
    
    # ルームに参加
    join_room(room_id)
    
    # 全プレイヤーに通知
    emit('player_joined', {
        'player_id': player_id,
        'username': username,
        'room_info': room
    }, room=room_id)
    
    print(f"Player {username} ({player_id}) joined room {room_id}")

@socketio.on('toggle_ready')
def handle_toggle_ready():
    """プレイヤーの準備状態を切り替え"""
    player_id = request.sid
    
    if player_id not in player_rooms:
        emit('error', {'message': '部屋に参加していません'})
        return
    
    room_id = player_rooms[player_id]
    room = rooms[room_id]
    
    # 準備状態を切り替え
    current_ready = room['player_info'][player_id]['ready']
    room['player_info'][player_id]['ready'] = not current_ready
    
    # 全プレイヤーに通知
    emit('player_ready_changed', {
        'player_id': player_id,
        'ready': not current_ready,
        'room_info': room
    }, room=room_id)
    
    # 全員が準備完了していれば、ゲーム開始可能な状態にする
    all_ready = all(info['ready'] for info in room['player_info'].values())
    if all_ready and len(room['players']) >= 2:
        emit('all_players_ready', {'room_info': room}, room=room_id)

@socketio.on('set_target_url')
def handle_set_target_url(data):
    """ホストが目標URLを設定"""
    player_id = request.sid
    room_id = data.get('room_id')
    raw_target_url = data.get('target_url')

    if not room_id or room_id not in rooms:
        emit('error', {'message': '部屋が見つかりません'})
        return

    room = rooms[room_id]

    if room['host'] != player_id:
        emit('error', {'message': 'ホストのみが目標URLを設定できます'})
        return

    if room['status'] != 'waiting':
        emit('error', {'message': 'ゲーム待機中のみ目標URLを設定できます'})
        return

    # ここで new_target_url のバリデーションを行うことが推奨されます
    # (例: 有効なWikipediaのURLか、など)
    if not is_safe_url(raw_target_url):
        emit('error', {'message': '目標URLが無効か、空です。WikipediaのURLを指定してください。'})
        return

    escaped_target_url = html.escape(raw_target_url) # WebSocketで送信する前にエスケープ
    room['target_url'] = raw_target_url # DBには元のURLを保存（表示時にエスケープするため）

    emit('target_url_updated', {
        'room_id': room_id,
        'target_url': escaped_target_url, # クライアントにはエスケープしたものを送信
        'room_info': room  # room_info内のtarget_urlもエスケープが必要な場合は別途対応
    }, room=room_id)
    print(f"Room {room_id} target URL set to: {raw_target_url}")

@socketio.on('update_room_settings')
def handle_update_room_settings(data):
    """ホストがルーム設定を更新"""
    player_id = request.sid
    room_id = data.get('room_id')
    settings_data = data.get('settings') # dataのキーを 'settings' に変更

    if not room_id or room_id not in rooms:
        emit('error', {'message': '部屋が見つかりません'})
        return

    room = rooms[room_id]

    if room['host'] != player_id:
        emit('error', {'message': 'ホストのみが設定を変更できます'})
        return

    if room['status'] != 'waiting':
        emit('error', {'message': 'ゲーム待機中のみ設定を変更できます'})
        return

    if settings_data:
        # 設定が初期化されていない場合は初期化
        if 'settings' not in room:
            room['settings'] = {'allow_ctrl_f': True, 'game_mode': 'navigation'}
            
        # Ctrl+F設定更新
        if 'allow_ctrl_f' in settings_data:
            room['settings']['allow_ctrl_f'] = bool(settings_data['allow_ctrl_f'])
            
        # ゲームモード設定更新
        if 'game_mode' in settings_data:
            if settings_data['game_mode'] in ['navigation', 'guessing']:
                room['settings']['game_mode'] = settings_data['game_mode']
    
    # 更新されたルーム情報をブロードキャスト
    # 'room_info' には更新された settings が含まれるようにする
    emit('room_settings_updated', {
        'room_id': room_id,
        'settings': room['settings'], # 個別の settings も送る
        'room_info': room # room全体も送る（これに settings が含まれる）
    }, room=room_id)
    print(f"Room {room_id} settings updated: {room['settings']}")

@socketio.on('start_game')
def handle_start_game():
    """ゲームを開始"""
    player_id = request.sid
    
    if player_id not in player_rooms:
        emit('error', {'message': '部屋に参加していません'})
        return
    
    room_id = player_rooms[player_id]
    room = rooms[room_id]
    
    # ホストのみがゲームを開始できる
    if room['host'] != player_id:
        emit('error', {'message': 'ホストのみがゲームを開始できます'})
        return
    
    # 全員の準備が完了していない場合はエラー
    all_ready = all(info['ready'] for info in room['player_info'].values() if player_id != room['host'])
    if not all_ready and len(room['players']) > 1:
        emit('error', {'message': '全員の準備が完了していません'})
        return
    
    # 最低2人必要
    if len(room['players']) < 2:
        emit('error', {'message': '最低2人のプレイヤーが必要です'})
        return
    
    # ランダムなスタートページとターゲットページを生成
    start_url = get_random_wikipedia_page() # これはWikipediaなので安全
    # room['target_url'] は is_safe_url で検証済み
    target_url = room.get('target_url', 'https://ja.wikipedia.org/wiki/日本')
    
    # ゲーム状態を初期化
    game_states[room_id] = {
        'start_url': start_url, # 安全なURL
        'target_url': target_url, # 安全なURL
        'player_states': {
            player_id: {
                'current_url': start_url, # 安全なURL
                'moves': 0,
                'path': [start_url],
                'finished': False,
                'finish_time': None,
                'eliminated': False # 脱落フラグ
            } for player_id in room['players']
        },
        'started_at': time.time(), # ゲーム開始時刻を記録
        'finished': False
    }
    
    # 部屋のステータスを更新
    room['status'] = 'playing'
    
    # 全プレイヤーに通知
    emit('game_started', {
        'start_url': html.escape(start_url),
        'target_url': html.escape(target_url),
        'game_state': game_states[room_id], # game_state内のURLも必要に応じてエスケープ
        'room_info': room,
        'room_settings': room.get('settings', {'allow_ctrl_f': True}) # ルーム設定も送信
    }, room=room_id)
    
    print(f"Game started in room {room_id}")

@socketio.on('player_move')
def handle_player_move(data):
    """プレイヤーの移動を処理"""
    player_id = request.sid
    raw_url = data.get('url')

    if not is_safe_url(raw_url):
        emit('error', {'message': '無効な移動先URLです。'})
        return
    
    url = raw_url # 検証済みなのでそのまま使用

    if not player_id in player_rooms:
        emit('error', {'message': '部屋に参加していません'})
        return
    
    room_id = player_rooms[player_id]
    
    if room_id not in game_states:
        emit('error', {'message': 'ゲームが開始されていません'})
        return
    
    game_state = game_states[room_id]
    player_state = game_state['player_states'][player_id]
    
    # プレイヤーが既にゴールしているか、脱落している場合は何もしない
    if player_state['finished'] or player_state.get('eliminated', False):
        return
    
    # 移動回数を増やす
    player_state['moves'] += 1
    player_state['current_url'] = url
    player_state['path'].append(url)
    
    # 目標に到達したかチェック
    target_url = game_state['target_url']
    from urllib.parse import urlparse, unquote
    current_path = unquote(urlparse(url).path)
    target_path = unquote(urlparse(target_url).path)
    is_target = current_path.lower() == target_path.lower()
    
    if is_target:
        import time
        player_state['finished'] = True
        player_state['finish_time'] = time.time()
        
        # すべてのプレイヤーがゴールしたかチェック
        all_finished = all(state['finished'] for state in game_state['player_states'].values())
        
        if all_finished:
            game_state['finished'] = True
            rooms[room_id]['status'] = 'finished'
    
    # 全プレイヤーに通知
    emit('player_moved', {
        'player_id': player_id,
        'url': html.escape(url),
        'moves': player_state['moves'],
        'finished': player_state['finished'],
        'game_state': game_state
    }, room=room_id)
    
    # プレイヤーがゴールした場合は追加の通知
    # プレイヤーがゴールした場合は追加の通知
    if is_target:
        # 順位を計算
        # ゴールしたプレイヤーのリストを取得
        finished_player_ids = [p_id for p_id, state in game_state['player_states'].items() if state['finished']]
        
        # 移動回数が少ない順、同じ場合はゴール時間が早い順でソート
        finished_player_ids.sort(key=lambda p_id: (
            game_state['player_states'][p_id]['moves'],
            game_state['player_states'][p_id]['finish_time']
        ))
        
        # 現在のプレイヤーの順位を取得
        try:
            rank = finished_player_ids.index(player_id) + 1
        except ValueError:
            rank = -1 # 万が一リストにない場合（通常はありえない）

        emit('player_finished', {
            'player_id': player_id,
            'rank': rank,
            'moves': player_state['moves'],
            'finished_players': finished_player_ids, # ソート済みのIDリスト
            'game_state': game_state
        }, room=room_id)
        
        # 全員がゴールした場合はゲーム終了の通知
        if all_finished:
            # 最終結果を作成
            results = []
            for i, p_id in enumerate(finished_player_ids):
                p_state = game_state['player_states'][p_id]
                p_info = rooms[room_id]['player_info'][p_id]
                time_taken = None
                if p_state['finished'] and p_state['finish_time'] and game_state['started_at']:
                    time_taken = p_state['finish_time'] - game_state['started_at']

                results.append({
                    'player_id': p_id,
                    'username': html.escape(p_info['username']), # usernameをエスケープ
                    'moves': p_state['moves'],
                    'path': [html.escape(p) for p in p_state['path']], # path内の各URLをエスケープ
                    'rank': i + 1, # ソート順に基づいたランク
                    'time_taken': time_taken
                })
            
            emit('game_finished', {
                'results': results,
                'game_state': game_state
            }, room=room_id)

@socketio.on('ctrl_f_violation')
def handle_ctrl_f_violation():
    """Ctrl+F違反を処理し、プレイヤーを脱落させる"""
    player_id = request.sid
    if player_id not in player_rooms:
        emit('error', {'message': '部屋に参加していません'})
        return

    room_id = player_rooms[player_id]
    if room_id not in rooms or room_id not in game_states:
        emit('error', {'message': 'ゲームがアクティブではありません'})
        return

    room = rooms[room_id]
    game_state = game_states[room_id]
    player_state = game_state['player_states'].get(player_id)

    # Ctrl+Fが禁止されているか確認
    if room.get('settings', {}).get('allow_ctrl_f', True):
        # 許可されている場合は何もしない（念のため）
        return

    if player_state and not player_state.get('eliminated', False) and not player_state['finished']:
        player_state['eliminated'] = True
        player_state['finished'] = True # 脱落もゴール扱いとする
        player_state['finish_time'] = time.time()
        # player_state['moves'] はそのまま

        print(f"Player {player_id} in room {room_id} was eliminated for Ctrl+F violation.")

        # 全プレイヤーに通知 (player_moved と同様の形式でゲーム状態を更新)
        emit('player_eliminated', { # 新しいイベントタイプ
            'player_id': player_id,
            'game_state': game_state,
            'elimination_reason': 'Ctrl+F violation'
        }, room=room_id)

        # 全員が終了（または脱落）したかチェック
        all_players_done = all(
            ps.get('finished', False) for ps in game_state['player_states'].values()
        )
        if all_players_done:
            game_state['finished'] = True
            room['status'] = 'finished'
            # ここで game_finished イベントを発行することもできるが、
            # player_finished のロジックと重複するため、
            # player_eliminated を受け取ったクライアント側で結果表示を促すか、
            # 共通の終了処理を呼び出す形が良いかもしれない。
            # 今回は player_eliminated で game_state を送るので、クライアントはそれに基づいて判断する。
            # 必要であれば、ここで game_finished と同様の結果集計と送信を行う。
            # 例えば、最後のプレイヤーが脱落してゲームが終わる場合など。
            # ひとまず、player_eliminated で game_state を送ることで対応。
            # もし全員が脱落またはゴールしたら、最終結果を送信する
            if all(state.get('finished') for state in game_state['player_states'].values()):
                # 最終結果を作成 (handle_player_move からロジックを再利用または共通化)
                finished_player_ids = [p_id for p_id, state in game_state['player_states'].items() if state['finished']]
                finished_player_ids.sort(key=lambda p_id: (
                    game_state['player_states'][p_id]['moves'],
                    game_state['player_states'][p_id]['finish_time']
                ))
                results = []
                for i, p_id_res in enumerate(finished_player_ids): # p_id だと外側のスコープと被る可能性
                    p_state_res = game_state['player_states'][p_id_res]
                    p_info_res = rooms[room_id]['player_info'][p_id_res]
                    time_taken_res = None
                    if p_state_res['finished'] and p_state_res['finish_time'] and game_state['started_at']:
                        time_taken_res = p_state_res['finish_time'] - game_state['started_at']
                    results.append({
                        'player_id': p_id_res,
                        'username': html.escape(p_info_res['username']),
                        'moves': p_state_res['moves'],
                        'path': [html.escape(p) for p in p_state_res['path']],
                        'rank': i + 1,
                        'time_taken': time_taken_res,
                        'eliminated': p_state_res.get('eliminated', False)
                    })
                emit('game_finished', {'results': results, 'game_state': game_state}, room=room_id)


@socketio.on('leave_room_request')
def handle_leave_room():
    """部屋から退出"""
    player_id = request.sid
    
    if player_id not in player_rooms:
        return
    
    room_id = player_rooms[player_id]
    
    if room_id in rooms:
        # 部屋から退出
        leave_room(room_id)
        rooms[room_id]['players'].remove(player_id)
        del rooms[room_id]['player_info'][player_id]
        
        # 部屋が空になったら削除
        if len(rooms[room_id]['players']) == 0:
            del rooms[room_id]
            if room_id in game_states:
                del game_states[room_id]
        else:
            # ホストが退出した場合は新しいホストを設定
            if rooms[room_id]['host'] == player_id and rooms[room_id]['players']:
                rooms[room_id]['host'] = rooms[room_id]['players'][0]
            
            # 残りのプレイヤーに通知
            emit('player_left', {
                'player_id': player_id,
                'room_info': rooms[room_id]
            }, room=room_id)
    
    # プレイヤーの部屋情報を削除
    del player_rooms[player_id]
    
    emit('left_room')

@socketio.on('get_available_rooms')
def handle_get_available_rooms():
    """利用可能な部屋の一覧を取得"""
    available_rooms = [
        {
            'id': room_id,
            'name': room_info['name'],
            'host': room_info['host'],
            'player_count': len(room_info['players']),
            'max_players': room_info['max_players'],
            'status': room_info['status']
        }
        for room_id, room_info in rooms.items()
        if room_info['status'] == 'waiting' and len(room_info['players']) < room_info['max_players']
    ]
    
    emit('available_rooms', {'rooms': available_rooms})

@socketio.on('reset_room')
def handle_reset_room(data):
    """ゲーム終了後、同じルームで新しいゲームを始めるためにルームをリセット"""
    player_id = request.sid
    room_id = data.get('room_id')
    
    if not player_id in player_rooms:
        emit('error', {'message': '部屋に参加していません'})
        return
    
    if not room_id or room_id not in rooms:
        emit('error', {'message': '部屋が見つかりません'})
        return
    
    room = rooms[room_id]
    
    # ホストだけがリセットできる
    if room['host'] != player_id:
        emit('error', {'message': 'ホストのみがゲームをリセットできます'})
        return
    
    # ゲームが終了している場合のみリセット可能
    if room['status'] != 'finished':
        emit('error', {'message': 'ゲームが終了している場合のみリセットできます'})
        return
    
    # ルームをリセット（ウェイティング状態に戻す）
    room['status'] = 'waiting'
    
    # 全プレイヤーの準備状態をリセット
    for pid in room['player_info']:
        room['player_info'][pid]['ready'] = False
    
    # ゲーム状態をクリア（必要に応じて）
    if room_id in game_states:
        del game_states[room_id]
    
    # 全プレイヤーに通知
    emit('room_reset', {
        'room_id': room_id,
        'room_info': room
    }, room=room_id)
    
    print(f"Room {room_id} has been reset for a new game")

# アプリケーション起動
if __name__ == '__main__':
    socketio.run(app, debug=True, port=5500)