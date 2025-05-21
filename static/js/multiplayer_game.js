// ソケット接続
let socket;
let playerId;
let roomId;
let isHost = false;
let username = '';
let moveCount = 0;
let guessCount = 0; // タイトル当てモードでの推測回数
let startUrl = '';
let targetUrl = '';
let currentPage = '';
let gamePath = [];
let roomSettings = {
    allow_ctrl_f: true, // デフォルトでCtrl+Fを許可
    game_mode: 'navigation' // デフォルトはナビゲーションモード
};
let ctrlFPenaltyMoves = 3; // Ctrl+F使用時の移動ペナルティ回数
let ctrlFWarningShown = false; // 違反警告表示フラグ（違反時ダイアログ用）

// Ctrl+F検出機能のグローバルハンドラー
function setupGlobalCtrlFDetection() {
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            // ゲーム中でCtrl+Fが禁止されている場合のみ処理
            if (gameScreen && !gameScreen.classList.contains('hidden') && roomSettings && !roomSettings.allow_ctrl_f) {
                e.preventDefault();
                e.stopPropagation();

                if (!ctrlFWarningShown) { // 違反時ダイアログの重複表示を防ぐ
                    socket.emit('ctrl_f_violation');
                    showCtrlFViolationDialog(); // 違反したことを伝えるダイアログ
                }
                return false;
            }
        }
    });
}

// Ctrl+F違反時の警告ダイアログを表示
function showCtrlFViolationDialog() {
    ctrlFWarningShown = true; // 違反ダイアログは一度だけ表示

    const dialog = document.createElement('div');
    dialog.className = 'modal';
    dialog.style.zIndex = '2000';

    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.maxWidth = '400px';
    content.style.backgroundColor = '#ffebee'; // 薄い赤色背景
    content.style.border = '2px solid #e57373';

    const title = document.createElement('h3');
    title.textContent = '⚠️ページ内検索使用検出';
    title.style.color = '#d32f2f';

    const message = document.createElement('p');
    message.textContent = 'このルームではページ内検索(Ctrl+F)は禁止されています。ルール違反により脱落となります。';
    message.style.marginBottom = '20px';

    const buttonDiv = document.createElement('div');
    buttonDiv.style.textAlign = 'center';

    const okButton = document.createElement('button');
    okButton.className = 'btn';
    okButton.textContent = '了解しました';
    okButton.style.backgroundColor = '#d32f2f';
    okButton.onclick = function () {
        dialog.remove();
    };

    buttonDiv.appendChild(okButton);
    content.appendChild(title);
    content.appendChild(message);
    content.appendChild(buttonDiv);
    dialog.appendChild(content);
    document.body.appendChild(dialog);
}

// Ctrl+F禁止の場合の開始時警告ダイアログ
function showCtrlFWarningDialog() {
    const dialog = document.createElement('div');
    dialog.className = 'modal'; // 既存のモーダルスタイルを流用
    dialog.style.zIndex = '2000'; // 他のモーダルより手前に

    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.maxWidth = '450px';
    content.style.backgroundColor = '#fff3e0'; // 薄い警告色 (オレンジ系)
    content.style.border = '2px solid #ffb74d'; // 警告色のボーダー

    const title = document.createElement('h3');
    title.innerHTML = '⚠️ ページ内検索 (Ctrl+F) について';
    title.style.color = '#f57c00';
    title.style.marginBottom = '15px';

    const message = document.createElement('p');
    message.innerHTML = 'このゲーム設定では、Wikipediaページ内での検索機能 (Ctrl+F または Command+F) の使用は<strong>禁止</strong>されています。<br><br>使用が検出された場合、<strong>ペナルティとして脱落</strong>となりますのでご注意ください。';
    message.style.lineHeight = '1.6';
    message.style.marginBottom = '25px';

    const buttonDiv = document.createElement('div');
    buttonDiv.style.textAlign = 'center';

    const okButton = document.createElement('button');
    okButton.className = 'btn';
    okButton.textContent = '理解しました';
    okButton.style.backgroundColor = '#f57c00';
    okButton.style.color = 'white';
    okButton.onclick = function () {
        dialog.remove();
    };

    buttonDiv.appendChild(okButton);
    content.appendChild(title);
    content.appendChild(message);
    content.appendChild(buttonDiv);
    dialog.appendChild(content);
    document.body.appendChild(dialog);
}

// ページ読み込み時にグローバルCtrl+F検出を設定
document.addEventListener('DOMContentLoaded', setupGlobalCtrlFDetection);

// 画面要素
const usernameScreen = document.getElementById('username-screen');
const lobbyScreen = document.getElementById('lobby-screen');
const roomScreen = document.getElementById('room-screen');
const gameScreen = document.getElementById('game-screen');
const resultsModal = document.getElementById('results-modal');

// ユーザー名入力
// ユーザー名をローカルストレージから読み込む
window.addEventListener('DOMContentLoaded', function() {
    const savedUsername = localStorage.getItem('wikigame_username');
    if (savedUsername) {
        document.getElementById('username-input').value = savedUsername;
        document.getElementById('submit-username').click();
    }
});

document.getElementById('submit-username').addEventListener('click', function () {
    username = document.getElementById('username-input').value.trim();
    if (username) {
        localStorage.setItem('wikigame_username', username);
        initSocketConnection();
        switchScreen(usernameScreen, lobbyScreen);
        loadAvailableRooms();
    } else {
        showToast('ユーザー名を入力してください', 'warning');
    }
});

// 名前を変更するボタンのイベントリスナー
document.getElementById('change-username-btn').addEventListener('click', function() {
    // 現在の名前を入力欄に設定
    document.getElementById('username-input').value = username;
    switchScreen(lobbyScreen, usernameScreen);
    // ソケット接続がある場合は切断
    if (socket && socket.connected) {
        socket.disconnect();
    }
});

function initSocketConnection() {
    socket = io();

    socket.on('connect', function () {
        console.log('Socket connected');
    });

    socket.on('connection_response', function (data) {
        playerId = data.player_id;
        console.log('Connected as', playerId);
    });

    // ルーム作成時のイベント
    socket.on('room_created', function (data) {
        roomId = data.room_id;
        isHost = true;
        switchScreen(lobbyScreen, roomScreen);
        updateRoomInfo(data.room_info);
    });

    socket.on('player_joined', function (data) {
        if (data.player_id === playerId && data.room_info && data.room_info.id) {
            roomId = data.room_info.id;
            switchScreen(lobbyScreen, roomScreen);
        }
        if (data.room_info && data.room_info.id === roomId) {
            updateRoomInfo(data.room_info);
        }
    });

    socket.on('player_ready_changed', function (data) {
        updateRoomInfo(data.room_info);
    });

    socket.on('all_players_ready', function (data) {
        if (isHost) {
            document.getElementById('start-game-btn').disabled = false;
        }
    });

    socket.on('target_url_updated', function (data) {
        if (data.room_id === roomId) {
            updateRoomInfo(data.room_info);
            if (data.room_info && data.room_info.target_url) {
                document.getElementById('current-room-target-url').textContent = decodeURIComponent(data.room_info.target_url).split('/').pop() || '未設定';
            }
            if (data.room_info && data.room_info.settings) {
                roomSettings = data.room_info.settings;
                updateCtrlFCheckbox(roomSettings.allow_ctrl_f);
            }
        }
    });

    socket.on('room_settings_updated', function (data) {
        if (data.room_id === roomId) {
            roomSettings = data.settings;
            updateRoomInfo(data.room_info);
        }
    });

    // ゲーム開始時のイベント
    socket.on('game_started', function (data) {
        if (data.room_settings) {
            roomSettings = data.room_settings; // roomSettingsをまず更新
        }
        startGame(data); // startGame関数は更新されたroomSettingsを参照する

        // ゲーム画面にCtrl+Fの許可状態を表示する
        const gameHeaderStats = document.querySelector('.game-header .game-stats');
        let ctrlFStatusDiv = document.getElementById('ctrl-f-status');
        if (!ctrlFStatusDiv && gameHeaderStats) {
            ctrlFStatusDiv = document.createElement('div');
            ctrlFStatusDiv.id = 'ctrl-f-status';
            ctrlFStatusDiv.className = 'game-stat';
            gameHeaderStats.appendChild(ctrlFStatusDiv);
        }
        if (ctrlFStatusDiv) {
            ctrlFStatusDiv.textContent = `ページ内検索: ${roomSettings.allow_ctrl_f ? '許可' : '禁止'}`;
            if (roomSettings && !roomSettings.allow_ctrl_f) {
                ctrlFStatusDiv.style.color = '#f44336'; // 禁止の場合は赤色
                ctrlFStatusDiv.style.fontWeight = 'bold'; // 禁止の場合は太字
            } else {
                ctrlFStatusDiv.style.color = ''; // 許可の場合はデフォルト色
                ctrlFStatusDiv.style.fontWeight = ''; // 許可の場合はデフォルトの太さ
            }
        }

        // Ctrl+Fが禁止の場合は開始時に警告ダイアログを表示
        if (roomSettings && !roomSettings.allow_ctrl_f) {
            showCtrlFWarningDialog();
        }

        // 違反検出用のフラグはリセット
        ctrlFWarningShown = false;
    });

    socket.on('player_eliminated', function (data) {
        if (data.game_state) {
            updateAllPlayersProgress(data.game_state);
        }

        if (data.player_id === playerId) {
            // showCtrlFViolationDialog() は setupGlobalCtrlFDetection 内で呼び出されるか、
            // サーバーからの明確な指示があった場合に呼び出す。
            // ここでは、脱落した旨をユーザーにシンプルに伝える。
            // alert(`ページ内検索の使用が検出されたため、脱落しました。理由: ${data.elimination_reason || '不明'}`);
            // もし違反ダイアログがまだ表示されていなければ表示する
            if (!ctrlFWarningShown) showCtrlFViolationDialog();

        } else {
            const playerName = getPlayerName(data.player_id, data.game_state); // game_stateを渡す
            showEliminationToast(playerName);
        }

        console.log('Player eliminated:', data.player_id, data.elimination_reason);
    });

    socket.on('player_moved', function (data) {
        updatePlayerProgress(data);
    });

    socket.on('player_finished', function (data) {
        playerFinished(data);
    });

    socket.on('game_finished', function (data) {
        showResults(data);
    });

    socket.on('player_left', function (data) {
        updateRoomInfo(data.room_info);
    });

    socket.on('left_room', function () {
        switchScreen(roomScreen, lobbyScreen);
        roomId = null;
        isHost = false;
        loadAvailableRooms();
    });

    socket.on('available_rooms', function (data) {
        displayAvailableRooms(data.rooms);
    });

    socket.on('room_reset', function (data) {
        if (data.room_id === roomId) {
            if (!gameScreen.classList.contains('hidden')) {
                switchScreen(gameScreen, roomScreen);
            }
            if (!resultsModal.classList.contains('hidden')) {
                resultsModal.classList.add('hidden');
            }
            updateRoomInfo(data.room_info);

            const toast = document.createElement('div');
            toast.style.position = 'fixed';
            toast.style.top = '20px';
            toast.style.left = '50%';
            toast.style.transform = 'translateX(-50%)';
            toast.style.backgroundColor = '#e8f5e9';
            toast.style.color = '#2e7d32';
            toast.style.padding = '10px 20px';
            toast.style.borderRadius = '5px';
            toast.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
            toast.style.fontWeight = 'bold';
            toast.style.zIndex = '9999';
            toast.innerHTML = '🔄 ルームがリセットされました。新しいゲームの準備をしてください。';

            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.5s ease';
                setTimeout(() => toast.remove(), 500);
            }, 3000);
        }
    });

    socket.on('error', function (data) {
        showToast(data.message, 'error');
    });
}

function loadAvailableRooms() {
    socket.emit('get_available_rooms');
}

function displayAvailableRooms(roomsData) { // 引数名を変更
    const roomsList = document.getElementById('rooms-list');
    roomsList.innerHTML = '';

    // roomsDataが配列でない、または空の場合はメッセージ表示
    if (!Array.isArray(roomsData) || roomsData.length === 0) {
        roomsList.innerHTML = '<p>利用可能なルームがありません</p>';
        return;
    }

    roomsData.forEach((room, index) => { // roomsData を使用
        const roomCard = document.createElement('div');
        roomCard.className = 'room-card';
        roomCard.style.animationDelay = `${index * 0.1}s`;

        const h3 = document.createElement('h3');
        h3.textContent = room.name;
        roomCard.appendChild(h3);

        const roomMetaDiv = document.createElement('div');
        roomMetaDiv.className = 'room-meta';

        const statusBadge = document.createElement('span');
        statusBadge.className = `status-badge ${room.status === 'waiting' ? 'waiting' : 'playing'}`;
        statusBadge.textContent = room.status === 'waiting' ? '待機中' : 'ゲーム中';
        roomMetaDiv.appendChild(statusBadge);

        const playersDiv = document.createElement('div');
        playersDiv.className = 'players';
        playersDiv.textContent = `${room.player_count} / ${room.max_players}人`;
        roomMetaDiv.appendChild(playersDiv);

        roomCard.appendChild(roomMetaDiv);

        roomCard.addEventListener('click', function () {
            socket.emit('join_room', {
                room_id: room.id,
                username: username
            });
        });

        roomsList.appendChild(roomCard);
    });
}

document.getElementById('create-room-btn').addEventListener('click', function () {
    socket.emit('create_room', {
        username: username
    });
});

document.getElementById('refresh-rooms-btn').addEventListener('click', function () {
    loadAvailableRooms();
});

function updateRoomInfo(roomInfo) {
    if (!roomInfo || !roomInfo.name) {
        console.warn('updateRoomInfo: roomInfo is invalid', roomInfo);
        return;
    }

    document.getElementById('room-name').textContent = roomInfo.name;

    const playersListElement = document.getElementById('players-list');
    playersListElement.innerHTML = '';

    if (roomInfo.player_info && roomInfo.players) {
        roomInfo.players.forEach(pId => {
            const playerInfo = roomInfo.player_info[pId];
            if (playerInfo) {
                const isHostPlayer = pId === roomInfo.host;

                const playerItem = document.createElement('div');
                playerItem.className = 'player-item';

                const usernameDiv = document.createElement('div');
                usernameDiv.className = 'username';
                usernameDiv.textContent = `${playerInfo.username} ${pId === playerId ? '(あなた)' : ''}`;
                playerItem.appendChild(usernameDiv);

                const statusDiv = document.createElement('div');
                statusDiv.className = `status ${playerInfo.ready ? 'ready' : (isHostPlayer ? 'host' : 'not-ready')}`;
                statusDiv.textContent = isHostPlayer ? 'ホスト' : (playerInfo.ready ? '準備完了' : '準備中');
                playerItem.appendChild(statusDiv);

                playersListElement.appendChild(playerItem);
            } else {
                console.warn(`Player info for ${pId} not found in room:`, roomInfo.id);
            }
        });
    } else {
        console.warn('Player info or players array is missing in roomInfo:', roomInfo);
    }

    const startGameBtn = document.getElementById('start-game-btn');
    if (playerId === roomInfo.host) {
        isHost = true;
        startGameBtn.style.display = 'block';

        const allNonHostPlayersReady = Object.entries(roomInfo.player_info)
            .filter(([id, p]) => id !== roomInfo.host) // ホスト自身は除く
            .every(([id, p]) => p.ready);

        // プレイヤーが2人以上いて、かつホスト以外の全員が準備完了なら開始可能
        startGameBtn.disabled = !(roomInfo.players.length >= 1 && allNonHostPlayersReady && roomInfo.target_url);
        // プレイヤー1人の場合でもテストできるように >=1 に変更 (通常は >=2)
        // 目標URLが設定されていることも条件に追加
    } else {
        isHost = false;
        startGameBtn.style.display = 'none';
    }

    const roomStatus = document.getElementById('room-status');
    roomStatus.textContent = `ステータス: ${roomInfo.status === 'waiting' ? '待機中' : 'ゲーム中'} - プレイヤー: ${roomInfo.players.length}/${roomInfo.max_players}`;
    document.getElementById('current-room-target-url').textContent = decodeURIComponent(roomInfo.target_url || 'https://ja.wikipedia.org/wiki/日本').split('/').pop() || '未設定';

    const targetUrlSettingDiv = document.getElementById('target-url-setting');
    if (isHost) {
        targetUrlSettingDiv.classList.remove('hidden');
        document.getElementById('room-target-url-input').value = roomInfo.target_url || '';
        const ctrlFCheckbox = document.getElementById('allow-ctrl-f-checkbox');
        ctrlFCheckbox.disabled = false;
        const gameModeSelect = document.getElementById('game-mode-select');
        gameModeSelect.disabled = false;

        if (roomInfo.settings) {
            ctrlFCheckbox.checked = roomInfo.settings.allow_ctrl_f;
            gameModeSelect.value = roomInfo.settings.game_mode || 'navigation';
        } else {
            ctrlFCheckbox.checked = true;
            gameModeSelect.value = 'navigation';
        }
    } else {
        targetUrlSettingDiv.classList.add('hidden');
        const ctrlFCheckbox = document.getElementById('allow-ctrl-f-checkbox');
        ctrlFCheckbox.disabled = true;
        const gameModeSelect = document.getElementById('game-mode-select');
        gameModeSelect.disabled = true;
        if (roomInfo.settings) {
            ctrlFCheckbox.checked = roomInfo.settings.allow_ctrl_f;
            gameModeSelect.value = roomInfo.settings.game_mode || 'navigation';
        } else {
            ctrlFCheckbox.checked = true;
            gameModeSelect.value = 'navigation';
        }
    }
}

function updateCtrlFCheckbox(isAllowed) {
    const ctrlFCheckbox = document.getElementById('allow-ctrl-f-checkbox');
    if (ctrlFCheckbox) {
        ctrlFCheckbox.checked = isAllowed;
        if (!isHost) {
            ctrlFCheckbox.disabled = true;
        }
    }
}

document.getElementById('toggle-ready-btn').addEventListener('click', function () {
    socket.emit('toggle_ready');
});

document.getElementById('set-target-url-btn').addEventListener('click', function () {
    const newTargetUrl = document.getElementById('room-target-url-input').value.trim();
    if (!newTargetUrl || !isValidWikipediaArticle(newTargetUrl)) {
        showToast('有効なWikipediaの目標ページURLを入力してください。', 'warning');
        return;
    }
    if (roomId) {
        socket.emit('set_target_url', { room_id: roomId, target_url: newTargetUrl });
    }
});

document.getElementById('allow-ctrl-f-checkbox').addEventListener('change', function () {
    if (isHost && roomId) {
        socket.emit('update_room_settings', {
            room_id: roomId,
            settings: { // 送信するsettingsオブジェクトを構築
                allow_ctrl_f: this.checked,
                game_mode: document.getElementById('game-mode-select').value // 現在のゲームモードも一緒に送る
            }
        });
    }
});

document.getElementById('game-mode-select').addEventListener('change', function () {
    if (isHost && roomId) {
        socket.emit('update_room_settings', {
            room_id: roomId,
            settings: { // 送信するsettingsオブジェクトを構築
                allow_ctrl_f: document.getElementById('allow-ctrl-f-checkbox').checked, // 現在のCtrl+F設定も一緒に送る
                game_mode: this.value
            }
        });
    }
});

document.getElementById('start-game-btn').addEventListener('click', function () {
    socket.emit('start_game');
});

document.getElementById('leave-room-btn').addEventListener('click', function () {
    socket.emit('leave_room_request');
});

function startGame(data) {
            switchScreen(roomScreen, gameScreen);

            startUrl = data.start_url;
            targetUrl = data.target_url;
            currentPage = startUrl;
            moveCount = 0;
            guessCount = 0; // 推測回数リセット
            gamePath = [startUrl];
            
            // プレイヤー進捗サイドバーを最初から表示
            document.getElementById('players-sidebar').classList.remove('hidden');

    document.getElementById('target-page-name').textContent = decodeURIComponent(targetUrl).split('/').pop();

    const gameMode = roomSettings.game_mode;
    if (gameMode === 'navigation') {
        document.getElementById('game-mode-display').textContent = 'モード: ナビゲーション';
        document.getElementById('navigation-target').classList.remove('hidden');
        document.getElementById('guessing-target').classList.add('hidden');
        document.getElementById('answer-form').classList.add('hidden');
        document.getElementById('game-moves').classList.remove('hidden');
        document.getElementById('game-guess-count').classList.add('hidden');
    } else if (gameMode === 'guessing') {
        document.getElementById('game-mode-display').textContent = 'モード: ページ名当て';
        document.getElementById('navigation-target').classList.add('hidden');
        document.getElementById('guessing-target').classList.remove('hidden');
        document.getElementById('answer-form').classList.remove('hidden');
        document.getElementById('game-moves').classList.add('hidden');
        document.getElementById('game-guess-count').classList.remove('hidden');
    }

    updateStats();

    let frameUrl;
    if (gameMode === 'guessing') {
        frameUrl = `/proxy?url=${encodeURIComponent(startUrl)}&mode=guessing&room_id=${roomId}`;
    } else {
        frameUrl = `/proxy?url=${encodeURIComponent(startUrl)}`;
    }
    document.getElementById('game-frame').src = frameUrl;

    updateAllPlayersProgress(data.game_state);
}

function updateStats() {
    if (roomSettings.game_mode === 'navigation') {
        document.getElementById('game-moves').textContent = `移動回数: ${moveCount}`;
        const pageName = currentPage ? decodeURIComponent(currentPage).split('/').pop() : '-';
        document.getElementById('current-page').textContent = `現在のページ: ${pageName}`;
    } else if (roomSettings.game_mode === 'guessing') {
        document.getElementById('game-guess-count').textContent = `推測回数: ${guessCount}`;
        document.getElementById('current-page').textContent = `現在のページ: ???`;
    }
}

document.getElementById('view-players-btn').addEventListener('click', function () {
    const sidebar = document.getElementById('players-sidebar');
    // 表示/非表示を切り替える代わりに、常に表示にする
    if (sidebar.classList.contains('hidden')) {
        sidebar.classList.remove('hidden');
    }
});

function updateAllPlayersProgress(gameState) {
    const progressList = document.getElementById('player-progress-list');
    progressList.innerHTML = '';

    // gameState.player_names はサーバーから送られてくる想定
    const playerNames = gameState.player_names || {};

    Object.entries(gameState.player_states).forEach(([pid, state], index) => {
        const playerCard = document.createElement('div');
        let cardClasses = 'player-card';
        if (state.finished) cardClasses += ' finished';
        if (pid === playerId) cardClasses += ' current-player';
        if (state.eliminated) cardClasses += ' eliminated';
        playerCard.className = cardClasses;
        playerCard.style.animationDelay = `${index * 0.1}s`;

        const rawPlayerName = playerNames[pid] || `プレイヤー${pid.substr(0, 4)}`;

        const playerNameDiv = document.createElement('div');
        playerNameDiv.className = 'player-name';

        const nameSpan = document.createElement('span');
        nameSpan.textContent = rawPlayerName;
        playerNameDiv.appendChild(nameSpan);

        const statusTextSpan = document.createElement('span');
        statusTextSpan.className = 'status-text';
        let statusTextContent = '';
        if (pid === playerId) statusTextContent += ' (あなた)';
        if (state.eliminated) {
            statusTextContent += ' (脱落)';
        } else if (state.finished) {
            if (roomSettings.game_mode === 'guessing' && state.correctly_guessed) {
                statusTextContent += ' (正解)';
            } else {
                statusTextContent += ' (ゴール)';
            }
        }
        statusTextSpan.textContent = statusTextContent.trim();
        if (statusTextSpan.textContent) {
            playerNameDiv.appendChild(document.createTextNode(' '));
            playerNameDiv.appendChild(statusTextSpan);
        }
        playerCard.appendChild(playerNameDiv);

        if (roomSettings.game_mode === 'navigation') {
            const playerMovesDiv = document.createElement('div');
            playerMovesDiv.className = 'player-info-item';
            const movesLabel = document.createElement('strong');
            movesLabel.textContent = '移動回数: ';
            playerMovesDiv.appendChild(movesLabel);
            playerMovesDiv.appendChild(document.createTextNode(state.moves));
            playerCard.appendChild(playerMovesDiv);

            const playerCurrentDiv = document.createElement('div');
            playerCurrentDiv.className = 'player-info-item';
            const currentLabel = document.createElement('strong');
            currentLabel.textContent = '現在: ';
            playerCurrentDiv.appendChild(currentLabel);
            const currentPageName = state.current_url ? decodeURIComponent(state.current_url).split('/').pop() : '-';
            playerCurrentDiv.appendChild(document.createTextNode(currentPageName));
            playerCard.appendChild(playerCurrentDiv);
        } else if (roomSettings.game_mode === 'guessing') {
            const playerGuessesDiv = document.createElement('div');
            playerGuessesDiv.className = 'player-info-item';
            const guessesLabel = document.createElement('strong');
            guessesLabel.textContent = '推測回数: ';
            playerGuessesDiv.appendChild(guessesLabel);
            playerGuessesDiv.appendChild(document.createTextNode(state.guesses_made || 0)); // gameStateから取得
            playerCard.appendChild(playerGuessesDiv);

            const statusDiv = document.createElement('div');
            statusDiv.className = 'player-info-item';
            const statusLabel = document.createElement('strong');
            statusLabel.textContent = '状態: ';
            statusDiv.appendChild(statusLabel);
            statusDiv.appendChild(document.createTextNode(state.correctly_guessed ? '正解済み' : '推測中'));
            playerCard.appendChild(statusDiv);
        }

        progressList.appendChild(playerCard);
    });
}

function updatePlayerProgress(data) {
    if (data.game_state && data.game_state.player_states && data.game_state.player_states[playerId]) {
        const myPlayerState = data.game_state.player_states[playerId];

        moveCount = myPlayerState.moves;
        currentPage = myPlayerState.current_url;
        gamePath = myPlayerState.path;
        if (roomSettings.game_mode === 'guessing') {
            guessCount = myPlayerState.guesses_made || 0;
        }
        updateStats();
    } else {
        if (data.player_id === playerId) {
            console.warn("My player state not found in game_state, using direct data from player_moved event.");
            moveCount = data.moves;
            currentPage = data.url;
            if (roomSettings.game_mode === 'guessing') {
                // guessCountはplayer_movedイベントでは直接更新されないため、game_stateに依存
            }
            updateStats();
        }
    }
    updateAllPlayersProgress(data.game_state);
}

function playerFinished(data) {
    if (data.player_id === playerId) {
        if (roomSettings.game_mode === 'navigation') {
            showToast(`目標達成！あなたは${data.rank}位です！`, 'success');
            // 目標ページに到達した場合、現在のページを更新
            currentPage = targetUrl;
            updateStats();
        }
        // Guessingモードの「ゴール」は answer_result で処理される
    }
    updateAllPlayersProgress(data.game_state);
}

function showResults(data) {
    const resultsTableBody = document.getElementById('results-table-body');
    resultsTableBody.innerHTML = '';

    const isGuessingMode = data.game_state.settings.game_mode === 'guessing';

    // ヘッダーをゲームモードに応じて変更
    const headerRow = resultsModal.querySelector('.leaderboard thead tr');
    headerRow.innerHTML = ''; // 一旦クリア
    const rankTh = document.createElement('th'); rankTh.textContent = '順位'; headerRow.appendChild(rankTh);
    const playerTh = document.createElement('th'); playerTh.textContent = 'プレイヤー'; headerRow.appendChild(playerTh);
    if (isGuessingMode) {
        const guessesTh = document.createElement('th'); guessesTh.textContent = '推測回数'; headerRow.appendChild(guessesTh);
    } else {
        const movesTh = document.createElement('th'); movesTh.textContent = '移動回数'; headerRow.appendChild(movesTh);
    }
    const timeTh = document.createElement('th'); timeTh.textContent = 'タイム'; headerRow.appendChild(timeTh);
    if (!isGuessingMode) { // ナビゲーションモードのみルート表示
        const routeTh = document.createElement('th'); routeTh.textContent = 'ルート'; headerRow.appendChild(routeTh);
    }


    data.results.forEach(result => {
        const row = document.createElement('tr');
        if (result.rank === 1) row.classList.add('rank-1');
        else if (result.rank === 2) row.classList.add('rank-2');
        else if (result.rank === 3) row.classList.add('rank-3');

        const timeTaken = result.time_taken ? formatTime(result.time_taken) : (result.eliminated || result.finished === false ? '-' : '計測不可');


        const rankTd = document.createElement('td');
        rankTd.className = 'rank';
        rankTd.textContent = result.eliminated ? '失格' : (result.rank || '-');
        row.appendChild(rankTd);

        const playerTd = document.createElement('td');
        let playerText = `${result.username} ${result.player_id === playerId ? '(あなた)' : ''}`;
        if (result.eliminated) {
            playerText += ' (脱落)';
            row.style.backgroundColor = '#ffebee';
        }
        playerTd.textContent = playerText;
        row.appendChild(playerTd);

        if (isGuessingMode) {
            const guessesTd = document.createElement('td');
            guessesTd.textContent = `${result.guesses_made !== undefined ? result.guesses_made : '-'}回`;
            row.appendChild(guessesTd);
        } else {
            const movesTd = document.createElement('td');
            movesTd.textContent = `${result.moves}回`;
            row.appendChild(movesTd);
        }

        const timeTd = document.createElement('td');
        timeTd.textContent = timeTaken;
        row.appendChild(timeTd);

        if (!isGuessingMode) {
            const pathTd = document.createElement('td');
            if (result.path && result.path.length > 0 && !result.eliminated) {
                const pathButton = document.createElement('button');
                pathButton.className = 'view-path-btn btn';
                pathButton.style.padding = '5px 10px';
                pathButton.style.fontSize = '0.8em';
                pathButton.textContent = 'ルート表示';
                pathButton.dataset.path = JSON.stringify(result.path);
                pathTd.appendChild(pathButton);
            } else {
                pathTd.textContent = '-';
            }
            row.appendChild(pathTd);
        }
        resultsTableBody.appendChild(row);
    });

    const modalContent = resultsModal.querySelector('.modal-content');
    let actionButtonsContainer = modalContent.querySelector('.action-buttons-container');
    if (!actionButtonsContainer) {
        actionButtonsContainer = document.createElement('div');
        actionButtonsContainer.className = 'action-buttons-container'; // クラス名で識別
        actionButtonsContainer.style.display = 'flex';
        actionButtonsContainer.style.justifyContent = 'center';
        actionButtonsContainer.style.gap = '15px';
        actionButtonsContainer.style.marginTop = '20px';
        modalContent.appendChild(actionButtonsContainer);
    }
    actionButtonsContainer.innerHTML = ''; // 既存のボタンをクリア

    const resetGameBtn = document.createElement('button');
    resetGameBtn.className = 'btn';
    resetGameBtn.style.backgroundColor = '#4CAF50';
    resetGameBtn.textContent = '新しいゲームを始める';
    resetGameBtn.onclick = resetGame;

    const backToLobbyBtnOriginal = document.getElementById('back-to-lobby-btn');
    const backToLobbyBtnClone = backToLobbyBtnOriginal.cloneNode(true); // イベントリスナーなしでクローン
    backToLobbyBtnClone.addEventListener('click', function () { // イベントリスナー再設定
        const mContent = resultsModal.querySelector('.modal-content');
        mContent.classList.remove('fade-in');
        mContent.classList.add('fade-out');

        setTimeout(() => {
            resultsModal.classList.add('hidden');
            mContent.classList.remove('fade-out');
            switchScreen(gameScreen, lobbyScreen);
            socket.emit('leave_room_request');
            loadAvailableRooms();
        }, parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--transition-speed')) * 1000);
    });

    actionButtonsContainer.appendChild(resetGameBtn);
    actionButtonsContainer.appendChild(backToLobbyBtnClone);

    document.querySelectorAll('.view-path-btn').forEach(button => {
        button.addEventListener('click', function () {
            const path = JSON.parse(this.dataset.path);
            displayPathInModal(path);
        });
    });

    createConfetti();

    resultsModal.classList.remove('hidden');
    modalContent.classList.add('fade-in');
}

function displayPathInModal(path) {
    const pathModal = document.createElement('div');
    pathModal.className = 'modal';
    pathModal.style.zIndex = '1001';

    const pathContent = document.createElement('div');
    pathContent.className = 'modal-content';
    pathContent.style.textAlign = 'left';

    const h2 = document.createElement('h2');
    h2.textContent = 'たどったルート';
    pathContent.appendChild(h2);

    const ol = document.createElement('ol');
    ol.style.paddingLeft = '20px';
    path.forEach(url => {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.textContent = decodeURIComponent(url).split('/').pop();
        li.appendChild(a);
        ol.appendChild(li);
    });
    pathContent.appendChild(ol);

    const closeButton = document.createElement('button');
    closeButton.className = 'btn';
    closeButton.textContent = '閉じる';
    closeButton.style.marginTop = '20px';
    closeButton.onclick = () => pathModal.remove();

    pathContent.appendChild(closeButton);
    pathModal.appendChild(pathContent);
    document.body.appendChild(pathModal);
}

function createConfetti() {
    const confettiCount = 100;
    const colors = ['#6e8efb', '#a777e3', '#ffcc00', '#ff7675', '#55efc4', '#00cec9'];
    const modalContent = document.querySelector('#results-modal .modal-content');

    if (!modalContent) {
        console.error('Modal content for confetti not found');
        return;
    }

    const existingConfetti = modalContent.querySelectorAll('.confetti');
    existingConfetti.forEach(c => c.remove());

    for (let i = 0; i < confettiCount; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.left = Math.random() * 100 + '%';
        confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        const size = Math.random() * 8 + 4;
        confetti.style.width = size + 'px';
        confetti.style.height = size * 1.5 + 'px';
        confetti.style.opacity = Math.random() * 0.6 + 0.4;

        confetti.style.animationName = 'common-confetti-fall'; // Use common animation name
        confetti.style.animationDuration = Math.random() * 2 + 3 + 's';
        confetti.style.animationDelay = Math.random() * 1.5 + 's';
        confetti.style.animationTimingFunction = 'ease-in';
        confetti.style.animationIterationCount = '1';
        confetti.style.animationFillMode = 'forwards';

        modalContent.appendChild(confetti);
    }
}

// ロビーに戻るボタンのオリジナルのイベントリスナーは showResults 内で再設定されるため、ここでは削除
// document.getElementById('back-to-lobby-btn').addEventListener('click', ...);

document.getElementById('game-frame').addEventListener('load', function () {
    const frame = this;

    try {
        const frameDoc = frame.contentDocument || frame.contentWindow.document;
        if (!frameDoc) { // クロスオリジンなどで frameDoc が取得できない場合
            console.warn('Cannot access iframe document. This might be due to cross-origin restrictions.');
            return;
        }

        const scripts = frameDoc.getElementsByTagName('script');
        Array.from(scripts).forEach(script => script.remove());

        if (roomSettings && roomSettings.allow_ctrl_f === false) {
            if (frame.contentWindow) {
                frame.contentWindow.addEventListener('keydown', function (e) {
                    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                        e.preventDefault();
                        console.log('Ctrl+F detected in iframe and is disallowed.');
                        if (!ctrlFWarningShown) { // 違反時ダイアログの重複表示を防ぐ
                            socket.emit('ctrl_f_violation');
                            showCtrlFViolationDialog();
                        }
                    }
                });
            } else {
                console.warn("Could not attach keydown listener to iframe: contentWindow is null.");
            }
        }

        const links = frameDoc.getElementsByTagName('a');
        Array.from(links).forEach(link => {
            link.addEventListener('click', async function (e) {
                e.preventDefault();
                const href = this.getAttribute('href');

                if (href) {
                    // 目次リンク(#で始まるアンカー)の場合は同じページ内ジャンプ
                    if (href.startsWith('#')) {
                        // 目次リンクをクリックした場合、同じページ内でスクロール
                        try {
                            const targetElement = frameDoc.querySelector(href);
                            if (targetElement) {
                                targetElement.scrollIntoView({ behavior: 'smooth' });
                            }
                        } catch (error) {
                            console.warn('目次リンクのスクロールエラー:', error);
                        }
                        return;
                    }
                    
                    let fullUrl;
                    if (href.startsWith('/wiki/')) {
                        fullUrl = `https://ja.wikipedia.org${href}`;
                    } else if (href.startsWith('http://') || href.startsWith('https://')) {
                        // URLオブジェクトでホスト名を確認
                        try {
                            const parsedUrl = new URL(href, frameDoc.baseURI); // 相対URL解決のためにbaseURIを指定
                            if (parsedUrl.hostname.endsWith('wikipedia.org')) {
                                fullUrl = parsedUrl.href;
                            } else {
                                console.log('External link clicked, ignoring:', href);
                                return; // Wikipedia以外のドメインは無視
                            }
                        } catch (urlError) {
                            console.warn('Invalid URL:', href, urlError);
                            return;
                        }
                    } else {
                        console.log('Non-standard link, ignoring:', href);
                        return;
                    }

                    if (isValidWikipediaArticle(fullUrl)) {
                        await navigateToPage(fullUrl);
                    } else {
                        console.log('無効なWikipediaリンクまたは非記事ページ:', fullUrl);
                        // ユーザーにフィードバックが必要ならここに追加
                    }
                }
            });
        });

        const style = frameDoc.createElement('style');
        style.textContent = `
            a { 
                cursor: pointer !important; 
                color: blue !important;
                text-decoration: underline !important;
            }
            a:hover { 
                text-decoration: underline !important; 
                color: darkblue !important;
            }
            /* 編集、ノート、履歴などのタブを非表示にする試み (もし必要なら) */
            #p-views ul, #p-cactions ul { display: none !important; }
            /* Wikipediaのロゴや検索バーを非表示 (もし必要なら) */
            #p-logo, #p-search { display: none !important; }
        `;
        frameDoc.head.appendChild(style);

    } catch (e) {
        // クロスオリジンエラーの場合、ここでキャッチされることが多い
        if (e.name === 'SecurityError') {
            console.warn('SecurityError: Cannot access iframe content. This is likely due to cross-origin policy.');
        } else {
            console.error('フレーム処理エラー:', e);
        }
    }
});

async function navigateToPage(clickedUrl) {
    socket.emit('player_move', {
        url: clickedUrl
    });

    let frameUrl;
    if (roomSettings.game_mode === 'guessing') {
        frameUrl = `/proxy?url=${encodeURIComponent(clickedUrl)}&mode=guessing&room_id=${roomId}`;
    } else {
        frameUrl = `/proxy?url=${encodeURIComponent(clickedUrl)}`;
    }
    document.getElementById('game-frame').src = frameUrl;
}

function isValidWikipediaArticle(url) {
    try {
        const urlObj = new URL(url);
        // ja.wikipedia.org 以外のドメインを弾く
        if (urlObj.hostname !== 'ja.wikipedia.org') {
            return false;
        }
        const path = urlObj.pathname;
        // /w/index.php 形式のURLも考慮 (例: /w/index.php?title=メインページ)
        if (path === '/w/index.php' && urlObj.searchParams.has('title')) {
            const title = urlObj.searchParams.get('title');
            return !title.includes(':') &&
                !title.startsWith('Special:') &&
                !title.startsWith('特別:') &&
                !title.startsWith('Wikipedia:') &&
                !title.startsWith('File:') &&
                !title.startsWith('ファイル:') &&
                !title.startsWith('Template:') &&
                !title.startsWith('テンプレート:');
        }

        return path.startsWith('/wiki/') &&
            !path.includes(':') && // 通常の記事名にはコロンは含まれないことが多い (ノートなどを除外)
            !path.startsWith('/wiki/Special:') &&
            !path.startsWith('/wiki/特別:') &&
            !path.startsWith('/wiki/Wikipedia:') &&
            !path.startsWith('/wiki/File:') &&
            !path.startsWith('/wiki/ファイル:') &&
            !path.startsWith('/wiki/Template:') &&
            !path.startsWith('/wiki/テンプレート:');
    } catch (e) {
        return false;
    }
}

function formatTime(seconds) {
    if (typeof seconds !== 'number' || isNaN(seconds)) return '-';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    const millis = Math.floor((remainingSeconds - Math.floor(remainingSeconds)) * 1000);
    return `${String(minutes).padStart(2, '0')}:${String(Math.floor(remainingSeconds)).padStart(2, '0')}.${String(millis).padStart(3, '0')}`;
}

function switchScreen(currentScreen, nextScreen) {
    if (currentScreen) {
        currentScreen.classList.add('fade-out');
        setTimeout(() => {
            currentScreen.classList.add('hidden');
            currentScreen.classList.remove('fade-out');
            if (nextScreen) {
                nextScreen.classList.remove('hidden');
                nextScreen.classList.add('fade-in');
                setTimeout(() => nextScreen.classList.remove('fade-in'), parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--transition-speed') || '0.3') * 1000);
            }
        }, parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--transition-speed') || '0.3') * 1000);
    } else if (nextScreen) {
        nextScreen.classList.remove('hidden');
        nextScreen.classList.add('fade-in');
        setTimeout(() => nextScreen.classList.remove('fade-in'), parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--transition-speed') || '0.3') * 1000);
    }
}

function getPlayerName(targetPlayerId, gameState) {
    // gameState.player_names が利用可能であればそれを使用
    if (gameState && gameState.player_names && gameState.player_names[targetPlayerId]) {
        return gameState.player_names[targetPlayerId];
    }
    // フォールバック (旧ロジックは rooms がグローバルでないため直接は使えない)
    return `プレイヤー (${targetPlayerId.substring(0, 4)}...)`;
}

function showEliminationToast(playerName) {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.backgroundColor = '#ffebee';
    toast.style.color = '#d32f2f';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '5px';
    toast.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';
    toast.style.zIndex = '9999';
    toast.style.maxWidth = '300px';
    toast.style.fontWeight = 'bold';
    toast.style.border = '1px solid #ef9a9a';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    // アニメーション用のCSSクラスを定義しておくとより管理しやすい
    // ここでは簡略化のため直接スタイル指定
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.5s ease-in-out';


    const icon = document.createElement('span');
    icon.innerHTML = '⚠️';
    icon.style.marginRight = '10px';
    icon.style.fontSize = '20px';

    const message = document.createElement('span');
    message.textContent = `${playerName} がCtrl+F使用のため脱落しました`;

    toast.appendChild(icon);
    toast.appendChild(message);
    document.body.appendChild(toast);

    // 表示アニメーション
    setTimeout(() => {
        toast.style.opacity = '1';
    }, 100); // 少し遅れて表示開始

    // 5秒後に消滅アニメーション開始
    setTimeout(() => {
        toast.style.opacity = '0';
        // アニメーション完了後に要素を削除
        setTimeout(() => {
            toast.remove();
        }, 500); // transitionの時間と合わせる
    }, 5000);
}

function resetGame() {
    const modalContent = resultsModal.querySelector('.modal-content');
    modalContent.classList.remove('fade-in');
    modalContent.classList.add('fade-out');

    setTimeout(() => {
        resultsModal.classList.add('hidden');
        modalContent.classList.remove('fade-out');
        // ゲーム画面から直接ルーム画面に戻るのではなく、
        // サーバーにルームリセットを要求し、サーバーからの 'room_reset' イベントで
        // 適切にUIを更新する。
        // switchScreen(gameScreen, roomScreen); // 直接の画面遷移は避ける

        socket.emit('reset_room', { room_id: roomId });

        // 準備完了状態のリセットは、サーバー側の 'room_reset' 処理に含めるか、
        // 'room_reset' イベント受信時にクライアント側で行うのが適切。
        // if (!isHost) {
        // socket.emit('toggle_ready');
        // }

    }, parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--transition-speed') || '0.3') * 1000);
}

// Enter キーでユーザー名を送信できるようにする
document.getElementById('username-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        document.getElementById('submit-username').click();
    }
});

document.getElementById('submit-answer-btn').addEventListener('click', function() {
    submitAnswer();
});

document.getElementById('answer-input').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        submitAnswer();
    }
});

function submitAnswer() {
    if (roomSettings.game_mode !== 'guessing') return;

    const answer = document.getElementById('answer-input').value.trim();
    if (!answer) return;

    socket.emit('submit_answer', {
        room_id: roomId,
        answer: answer,
        current_url: currentPage, // 現在のページのURLを送信
        // guess_count: guessCount // クライアント側のguessCountはサーバーで管理するため不要かも
    });

    document.getElementById('answer-input').value = '';
}

socket.on('answer_result', function (data) {
    // guessCount はサーバーからの game_state で更新されるので、ここでは直接更新しない
    // updateStats() は player_moved や game_state 受信時に呼ばれる

    if (data.is_correct) {
        showCorrectAnswerDialog(data.correct_title);
        // 自分の状態は game_state で更新されるのを待つ
    } else {
        showWrongAnswerDialog();
        // guessCount はサーバー側でインクリメントされ、game_state経由で更新される
        // クライアントで guessCount++ すると二重カウントの可能性
        // this.guessCount = data.new_guess_count; // サーバーから新しい推測回数を受け取るなら
        // updateStats();
    }
    // game_state が一緒に送られてくるなら、ここで updateAllPlayersProgress(data.game_state) を呼ぶ
    if (data.game_state) {
        updateAllPlayersProgress(data.game_state);
        // 自分のステータスも更新
        if (data.game_state.player_states && data.game_state.player_states[playerId]) {
            const myState = data.game_state.player_states[playerId];
            guessCount = myState.guesses_made || 0;
            updateStats();
        }
    }
});

socket.on('player_answered_correctly', function (data) {
    if (data.player_id !== playerId) {
        showPlayerAnsweredToast(data.player_name);
    }
    if (data.game_state) {
        updateAllPlayersProgress(data.game_state);
    }
});

function showCorrectAnswerDialog(correctTitle) {
    const dialog = document.createElement('div');
    dialog.className = 'modal';
    dialog.style.zIndex = '2000';

    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.maxWidth = '400px';
    content.style.backgroundColor = '#e8f5e9';
    content.style.border = '2px solid #4caf50';

    const title = document.createElement('h3');
    title.textContent = '🎉 正解！';
    title.style.color = '#2e7d32';

    const message = document.createElement('p');
    message.textContent = `正解は「${correctTitle}」でした！`;
    message.style.marginBottom = '20px';
    message.style.fontSize = '18px';

    const buttonDiv = document.createElement('div');
    buttonDiv.style.textAlign = 'center';

    const okButton = document.createElement('button');
    okButton.className = 'btn';
    okButton.textContent = 'OK'; // 「次へ」よりは「OK」が適切かも
    okButton.style.backgroundColor = '#4caf50';
    okButton.onclick = function () {
        dialog.remove();
        // 正解後、次のページへ自動遷移するか、サーバーからの指示を待つ
        // もしサーバーが次のページを指示するなら、ここで何かをする必要はない
        // もし次のランダムなページへ進むなら、その処理をここかサーバー応答で
    };

    buttonDiv.appendChild(okButton);
    content.appendChild(title);
    content.appendChild(message);
    content.appendChild(buttonDiv);
    dialog.appendChild(content);
    document.body.appendChild(dialog);
}

function showWrongAnswerDialog() {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.backgroundColor = '#ffebee';
    toast.style.color = '#d32f2f';
    toast.style.padding = '10px 20px';
    toast.style.borderRadius = '5px';
    toast.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
    toast.style.fontWeight = 'bold';
    toast.style.zIndex = '9999';
    toast.textContent = '❌ 不正解です。もう一度挑戦してください。';
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease-out';

    document.body.appendChild(toast);

    setTimeout(() => { toast.style.opacity = '1'; }, 50); // 表示アニメーション

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300); // 削除アニメーション後
    }, 2000);
}

function showPlayerAnsweredToast(playerName) {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.backgroundColor = '#e8f5e9';
    toast.style.color = '#2e7d32';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '5px';
    toast.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';
    toast.style.zIndex = '9999';
    toast.style.maxWidth = '300px';
    toast.style.fontWeight = 'bold';
    toast.style.border = '1px solid #a5d6a7';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.5s ease-in-out';

    const icon = document.createElement('span');
    icon.innerHTML = '🎯';
    icon.style.marginRight = '10px';
    icon.style.fontSize = '20px';

    const message = document.createElement('span');
    message.textContent = `${playerName} がページ名を当てました！`;

    toast.appendChild(icon);
    toast.appendChild(message);
    document.body.appendChild(toast);

    setTimeout(() => { toast.style.opacity = '1'; }, 100);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => { toast.remove(); }, 500);
    }, 5000);
}
