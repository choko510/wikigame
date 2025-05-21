from flask import request
from flask_socketio import emit, join_room, leave_room
from . import socketio # Import the socketio instance
from .models import rooms, player_rooms, game_states # Import your models
from .utils import get_random_wikipedia_page, is_safe_url # Import utils
import uuid
import time
import html # For escaping user inputs like usernames
from urllib.parse import urlparse, unquote


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
            if player_id in rooms[room_id]['players']: # Check if player is actually in the list
                rooms[room_id]['players'].remove(player_id)
            
            # 部屋が空になったら削除
            if not rooms[room_id]['players']: # Check if list is empty
                del rooms[room_id]
                if room_id in game_states:
                    del game_states[room_id]
            else:
                # ホストが退出した場合、新しいホストを選出 (必要であれば)
                if rooms[room_id]['host'] == player_id:
                    rooms[room_id]['host'] = rooms[room_id]['players'][0]
                # 残りのプレイヤーに通知
                emit('player_left', {'player_id': player_id, 'room_info': rooms[room_id]}, room=room_id)
        
        # プレイヤーの部屋情報を削除
        del player_rooms[player_id]
    
    print(f"Player disconnected: {player_id}")

@socketio.on('create_room')
def handle_create_room(data):
    """新しいゲームルームを作成"""
    player_id = request.sid
    raw_username = data.get('username', f'プレイヤー{random.randint(1000, 9999)}')
    username = html.escape(raw_username)
    
    room_id = str(uuid.uuid4())[:8]
    
    rooms[room_id] = {
        'id': room_id,
        'name': f"{username}の部屋",
        'host': player_id,
        'players': [player_id],
        'player_info': {player_id: {'username': username, 'ready': False}},
        'status': 'waiting',
        'max_players': 4,
        'target_url': 'https://ja.wikipedia.org/wiki/日本',
        'settings': {
            'allow_ctrl_f': True,
            'game_mode': 'navigation'
        }
    }
    
    player_rooms[player_id] = room_id
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
    
    if len(room['players']) >= room['max_players']:
        emit('error', {'message': '部屋が満員です'})
        return
    
    if room['status'] != 'waiting':
        emit('error', {'message': 'ゲームはすでに始まっています'})
        return
    
    room['players'].append(player_id)
    room['player_info'][player_id] = {'username': username, 'ready': False}
    player_rooms[player_id] = room_id
    join_room(room_id)
    
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
    
    current_ready = room['player_info'][player_id]['ready']
    room['player_info'][player_id]['ready'] = not current_ready
    
    emit('player_ready_changed', {
        'player_id': player_id,
        'ready': not current_ready,
        'room_info': room
    }, room=room_id)
    
    # ホスト以外の全プレイヤーが準備完了しているかチェック
    non_host_players = [pid for pid in room['players'] if pid != room['host']]
    all_non_host_ready = all(room['player_info'][pid]['ready'] for pid in non_host_players) if non_host_players else True


    # プレイヤーが1人（ホストのみ）の場合、またはホスト以外全員準備OKの場合
    # かつ、目標URLが設定されている場合にゲーム開始ボタンを有効化
    if room['host'] == player_id: # この通知はホストにのみ関係する
        if (len(room['players']) == 1 or all_non_host_ready) and room.get('target_url'):
             emit('all_players_ready', {'room_info': room}, room=room['host']) # ホストにのみ送信


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

    if not is_safe_url(raw_target_url): # utilsからインポートしたis_safe_urlを使用
        emit('error', {'message': '目標URLが無効か、空です。WikipediaのURLを指定してください。'})
        return

    room['target_url'] = raw_target_url 

    emit('target_url_updated', {
        'room_id': room_id,
        'target_url': html.escape(raw_target_url), 
        'room_info': room 
    }, room=room_id)
    print(f"Room {room_id} target URL set to: {raw_target_url}")

@socketio.on('update_room_settings')
def handle_update_room_settings(data):
    """ホストがルーム設定を更新"""
    player_id = request.sid
    room_id = data.get('room_id')
    settings_data = data.get('settings')

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
        if 'settings' not in room: # Should always exist based on room creation
            room['settings'] = {'allow_ctrl_f': True, 'game_mode': 'navigation'}
            
        if 'allow_ctrl_f' in settings_data:
            room['settings']['allow_ctrl_f'] = bool(settings_data['allow_ctrl_f'])
            
        if 'game_mode' in settings_data:
            if settings_data['game_mode'] in ['navigation', 'guessing']:
                room['settings']['game_mode'] = settings_data['game_mode']
    
    emit('room_settings_updated', {
        'room_id': room_id,
        'settings': room['settings'], 
        'room_info': room 
    }, room=room_id)
    print(f"Room {room_id} settings updated: {room['settings']}")


@socketio.on('start_game')
def handle_start_game():
    player_id = request.sid
    if player_id not in player_rooms:
        emit('error', {'message': '部屋に参加していません'})
        return
    
    room_id = player_rooms[player_id]
    room = rooms[room_id]
    
    if room['host'] != player_id:
        emit('error', {'message': 'ホストのみがゲームを開始できます'})
        return
    
    # ホスト以外のプレイヤーが全員準備完了しているか、またはプレイヤーがホスト1人のみか
    non_host_players = [pid for pid in room['players'] if pid != room['host']]
    all_non_host_ready = all(room['player_info'][pid]['ready'] for pid in non_host_players) if non_host_players else True # True if no non-host players

    if not (len(room['players']) == 1 or all_non_host_ready) :
         emit('error', {'message': 'ホスト以外の全員の準備が完了していません'})
         return

    # プレイヤー数が1人以上（テスト用に変更、本番では2人以上に戻すことを検討）
    if len(room['players']) < 1: # Changed from < 2 for single player host testing
        emit('error', {'message': '最低1人のプレイヤーが必要です'}) # Changed message
        return

    if not room.get('target_url'):
        emit('error', {'message': '目標ページが設定されていません'})
        return

    start_url = get_random_wikipedia_page() # utilsからインポート
    target_url = room['target_url'] # Validation already done by is_safe_url in set_target_url
    
    game_states[room_id] = {
        'start_url': start_url,
        'target_url': target_url,
        'player_states': {
            pid: { # Corrected from player_id to pid
                'current_url': start_url,
                'moves': 0,
                'path': [start_url],
                'finished': False,
                'finish_time': None,
                'eliminated': False,
                'guesses_made': 0 # For guessing mode
            } for pid in room['players']
        },
        'started_at': time.time(),
        'finished': False,
        'settings': room.get('settings', {'allow_ctrl_f': True, 'game_mode': 'navigation'}) # Store settings at game start
    }
    
    room['status'] = 'playing'
    
    emit('game_started', {
        'start_url': html.escape(start_url),
        'target_url': html.escape(target_url),
        'game_state': game_states[room_id],
        'room_info': room, # Contains current settings
        'room_settings': game_states[room_id]['settings'] # Send game-specific settings
    }, room=room_id)
    print(f"Game started in room {room_id}")

@socketio.on('player_move')
def handle_player_move(data):
    player_id = request.sid
    raw_url = data.get('url')

    if not is_safe_url(raw_url): # utilsからインポート
        emit('error', {'message': '無効な移動先URLです。'})
        return
    
    url = raw_url

    if player_id not in player_rooms:
        emit('error', {'message': '部屋に参加していません'})
        return
    
    room_id = player_rooms[player_id]
    
    if room_id not in game_states:
        emit('error', {'message': 'ゲームが開始されていません'})
        return
    
    game_state = game_states[room_id]
    player_state = game_state['player_states'][player_id]
    
    if player_state['finished'] or player_state.get('eliminated', False):
        return
    
    player_state['moves'] += 1
    player_state['current_url'] = url
    player_state['path'].append(url)
    
    target_url = game_state['target_url']
    current_path = unquote(urlparse(url).path)
    target_path = unquote(urlparse(target_url).path)
    is_target = current_path.lower() == target_path.lower()
    
    if is_target:
        player_state['finished'] = True
        player_state['finish_time'] = time.time()
        
    emit('player_moved', {
        'player_id': player_id,
        'url': html.escape(url),
        'moves': player_state['moves'],
        'finished': player_state['finished'],
        'game_state': game_state
    }, room=room_id)
    
    if is_target:
        finished_player_ids = [pid for pid, p_state in game_state['player_states'].items() if p_state['finished']]
        finished_player_ids.sort(key=lambda pid_sort: (
            game_state['player_states'][pid_sort]['moves'],
            game_state['player_states'][pid_sort]['finish_time']
        ))
        try:
            rank = finished_player_ids.index(player_id) + 1
        except ValueError:
            rank = -1

        emit('player_finished', {
            'player_id': player_id,
            'rank': rank,
            'moves': player_state['moves'],
            'finished_players': finished_player_ids,
            'game_state': game_state
        }, room=room_id)
        
        all_players_done = all(ps.get('finished', False) or ps.get('eliminated', False) for ps in game_state['player_states'].values())
        if all_players_done:
            game_state['finished'] = True
            rooms[room_id]['status'] = 'finished'
            results = []
            # Sort players by rank (moves, then time) for results
            sorted_player_ids = sorted(
                game_state['player_states'].keys(),
                key=lambda pid_sort: (
                    game_state['player_states'][pid_sort]['moves'],
                    game_state['player_states'][pid_sort].get('finish_time', float('inf')) # Eliminated players might not have finish_time
                )
            )
            rank_counter = 1
            for p_id_res in sorted_player_ids:
                p_state_res = game_state['player_states'][p_id_res]
                p_info_res = rooms[room_id]['player_info'][p_id_res]
                time_taken_res = None
                current_rank = rank_counter if p_state_res.get('finished') and not p_state_res.get('eliminated') else None
                if p_state_res.get('finished') and p_state_res.get('finish_time') and game_state.get('started_at'):
                    time_taken_res = p_state_res['finish_time'] - game_state['started_at']
                
                results.append({
                    'player_id': p_id_res,
                    'username': html.escape(p_info_res['username']),
                    'moves': p_state_res['moves'],
                    'guesses_made': p_state_res.get('guesses_made', 0), # Include guesses
                    'path': [html.escape(p) for p in p_state_res['path']],
                    'rank': current_rank,
                    'time_taken': time_taken_res,
                    'eliminated': p_state_res.get('eliminated', False),
                    'finished': p_state_res.get('finished', False) 
                })
                if current_rank is not None:
                    rank_counter +=1

            socketio.emit('game_finished', {'results': results, 'game_state': game_state}, room=room_id)


@socketio.on('ctrl_f_violation')
def handle_ctrl_f_violation():
    player_id = request.sid
    if player_id not in player_rooms: return
    room_id = player_rooms[player_id]
    if room_id not in rooms or room_id not in game_states: return

    room = rooms[room_id]
    game_state = game_states[room_id]
    player_state = game_state['player_states'].get(player_id)

    if room.get('settings', {}).get('allow_ctrl_f', True): return

    if player_state and not player_state.get('eliminated', False) and not player_state['finished']:
        player_state['eliminated'] = True
        player_state['finished'] = True 
        player_state['finish_time'] = time.time() 

        emit('player_eliminated', {
            'player_id': player_id,
            'game_state': game_state,
            'elimination_reason': 'Ctrl+F violation'
        }, room=room_id)

        all_players_done = all(ps.get('finished', False) for ps in game_state['player_states'].values())
        if all_players_done:
            game_state['finished'] = True
            room['status'] = 'finished'
            # Logic for creating and emitting results (similar to player_move)
            finished_player_ids = [pid for pid, p_state in game_state['player_states'].items() if p_state.get('finished', False)]
            finished_player_ids.sort(key=lambda pid_sort: (
                game_state['player_states'][pid_sort]['moves'],
                game_state['player_states'][pid_sort].get('finish_time', float('inf'))
            ))
            results = []
            rank_counter = 1
            for p_id_res in finished_player_ids:
                p_state_res = game_state['player_states'][p_id_res]
                p_info_res = rooms[room_id]['player_info'][p_id_res]
                time_taken_res = None
                current_rank = rank_counter if p_state_res.get('finished') and not p_state_res.get('eliminated') else None

                if p_state_res.get('finished') and p_state_res.get('finish_time') and game_state.get('started_at'):
                    time_taken_res = p_state_res['finish_time'] - game_state['started_at']
                
                results.append({
                    'player_id': p_id_res,
                    'username': html.escape(p_info_res['username']),
                    'moves': p_state_res['moves'],
                    'guesses_made': p_state_res.get('guesses_made', 0),
                    'path': [html.escape(p) for p in p_state_res['path']],
                    'rank': current_rank,
                    'time_taken': time_taken_res,
                    'eliminated': p_state_res.get('eliminated', False),
                    'finished': p_state_res.get('finished', False) 
                })
                if current_rank is not None:
                    rank_counter +=1
            socketio.emit('game_finished', {'results': results, 'game_state': game_state}, room=room_id)


@socketio.on('leave_room_request')
def handle_leave_room():
    player_id = request.sid
    if player_id not in player_rooms: return
    room_id = player_rooms[player_id]
    
    if room_id in rooms:
        room = rooms[room_id]
        if player_id in room['players']:
            room['players'].remove(player_id)
        if player_id in room['player_info']:
            del room['player_info'][player_id]
        
        if not room['players']:
            del rooms[room_id]
            if room_id in game_states: del game_states[room_id]
        else:
            if room['host'] == player_id:
                room['host'] = room['players'][0]
            emit('player_left', {'player_id': player_id, 'room_info': room}, room=room_id)
    
    if player_id in player_rooms: # Check before deleting
        del player_rooms[player_id]
    
    emit('left_room')

@socketio.on('get_available_rooms')
def handle_get_available_rooms():
    available_rooms_list = []
    for room_id, room_info in rooms.items():
        if room_info['status'] == 'waiting' and len(room_info['players']) < room_info['max_players']:
            available_rooms_list.append({
                'id': room_id,
                'name': room_info['name'],
                # 'host': room_info['host'], # Not typically needed for room list display
                'player_count': len(room_info['players']),
                'max_players': room_info['max_players'],
                'status': room_info['status']
            })
    emit('available_rooms', {'rooms': available_rooms_list})

@socketio.on('reset_room')
def handle_reset_room(data):
    player_id = request.sid
    room_id = data.get('room_id')
    
    if player_id not in player_rooms: return
    if not room_id or room_id not in rooms: return
    
    room = rooms[room_id]
    if room['host'] != player_id:
        emit('error', {'message': 'ホストのみがゲームをリセットできます'})
        return
    
    # Allow reset from 'playing' or 'finished' status
    if room['status'] not in ['playing', 'finished']:
        emit('error', {'message': 'ゲームが終了しているかプレイ中である場合のみリセットできます'})
        return
    
    room['status'] = 'waiting'
    for pid_info in room['player_info']: # Corrected iteration
        room['player_info'][pid_info]['ready'] = False
    
    if room_id in game_states: del game_states[room_id]
    
    emit('room_reset', {'room_id': room_id, 'room_info': room}, room=room_id)
    print(f"Room {room_id} has been reset for a new game")

@socketio.on('submit_answer') # For guessing mode
def handle_submit_answer(data):
    player_id = request.sid
    room_id = data.get('room_id')
    answer = data.get('answer', '').strip()
    current_page_url = data.get('current_url') # URL of the page being guessed

    if not player_id in player_rooms or room_id not in rooms or room_id not in game_states:
        emit('error', {'message': '無効なリクエストです。'})
        return

    game_state = game_states[room_id]
    player_state = game_state['player_states'].get(player_id)
    room = rooms[room_id]

    if not player_state or player_state.get('eliminated') or player_state.get('finished'):
        return # Player cannot submit if eliminated or already finished guessing correctly

    if room.get('settings', {}).get('game_mode') != 'guessing':
        emit('error', {'message': 'このルームはページ名当てモードではありません。'})
        return

    player_state['guesses_made'] = player_state.get('guesses_made', 0) + 1
    
    # Retrieve the correct page title stored during proxying
    # The key in current_pages should be the full URL of the page being guessed
    correct_title = room.get('current_pages', {}).get(current_page_url, "").strip()
    
    is_correct = False
    if answer.lower() == correct_title.lower(): # Case-insensitive comparison
        is_correct = True
        player_state['finished'] = True # Mark as finished for this page
        player_state['finish_time'] = time.time() # Record time for tie-breaking if needed
        # Potentially add to score or specific 'correctly_guessed_pages' list if game involves multiple pages

    emit('answer_result', {
        'player_id': player_id,
        'is_correct': is_correct,
        'correct_title': correct_title if is_correct else None, # Only send correct title if guessed
        'guesses_made': player_state['guesses_made'],
        'game_state': game_state
    }, room=request.sid) # Send result only to the player who answered

    if is_correct:
        # Notify others that a player answered correctly
        emit('player_answered_correctly', {
            'player_id': player_id,
            'player_name': html.escape(room['player_info'][player_id]['username']),
            'game_state': game_state
        }, room=room_id, include_self=False)

        # Check if all players have finished (guessed correctly or eliminated)
        all_players_done = all(ps.get('finished', False) or ps.get('eliminated', False) for ps in game_state['player_states'].values())
        if all_players_done:
            game_state['finished'] = True
            room['status'] = 'finished'
            # Construct and send final game results (similar to navigation mode)
            # This part can be refactored into a common function
            results = []
            sorted_player_ids = sorted(
                game_state['player_states'].keys(),
                key=lambda pid_sort: (
                    not game_state['player_states'][pid_sort].get('eliminated', False), # Prioritize not eliminated
                    game_state['player_states'][pid_sort].get('guesses_made', float('inf')),
                    game_state['player_states'][pid_sort].get('finish_time', float('inf'))
                ),
                reverse=False # False for ascending sort (fewer guesses are better)
            )
            rank_counter = 1
            for p_id_res in sorted_player_ids:
                p_state_res = game_state['player_states'][p_id_res]
                p_info_res = rooms[room_id]['player_info'][p_id_res]
                time_taken_res = None
                current_rank = None
                if p_state_res.get('finished') and not p_state_res.get('eliminated'):
                    current_rank = rank_counter
                    rank_counter +=1
                if p_state_res.get('finished') and p_state_res.get('finish_time') and game_state.get('started_at'):
                     time_taken_res = p_state_res['finish_time'] - game_state['started_at']

                results.append({
                    'player_id': p_id_res,
                    'username': html.escape(p_info_res['username']),
                    'moves': p_state_res['moves'], # Moves might still be relevant if game combines modes
                    'guesses_made': p_state_res.get('guesses_made', 0),
                    'path': [html.escape(p) for p in p_state_res['path']],
                    'rank': current_rank,
                    'time_taken': time_taken_res,
                    'eliminated': p_state_res.get('eliminated', False),
                    'finished': p_state_res.get('finished', False)
                })
            socketio.emit('game_finished', {'results': results, 'game_state': game_state}, room=room_id)
