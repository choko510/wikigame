let startUrl = '';
let targetUrl = 'https://ja.wikipedia.org/wiki/日本';
let targetPath = '/wiki/日本'; // パス部分のみ（URLパース用）
let moveCount = 0;
let guessCount = 0; // 推測回数
let availableLinks = [];
let currentPage = '';
let gamePath = []; // 移動の履歴を保存
let gameResults = []; // 過去のゲーム結果を保存
let gameType = 'navigation'; // ゲームモード: 'navigation' または 'guessing'
let correctPageTitle = ''; // 当てるべきページタイトル（ページ名当てモード用）

function updateStats() {
    if (gameType === 'navigation') {
        document.getElementById('moves').textContent = `移動回数: ${moveCount}`;
        const pageName = currentPage ? decodeURIComponent(currentPage).split('/').pop() : '-';
        document.getElementById('current-page').textContent = `現在のページ: ${pageName}`;
    } else if (gameType === 'guessing') {
        document.getElementById('guess-count').textContent = `推測回数: ${guessCount}`;
        // ページ名当てモードでは現在のページ名を表示しない
        document.getElementById('current-page').textContent = `現在のページ: ???`;
    }
}

// ゲームタイプを設定する関数
function setGameType(type) {
    gameType = type;
    
    // ボタンの見た目を更新
    const typeBtns = document.querySelectorAll('.type-btn');
    typeBtns.forEach((btn, index) => {
        btn.classList.remove('active');
        btn.style.background = '#f0f0f0';
        btn.style.color = '#333';
    });
    
    // 選択されたボタンをアクティブにする
    const activeIndex = type === 'navigation' ? 0 : 1;
    typeBtns[activeIndex].classList.add('active');
    typeBtns[activeIndex].style.background = 'linear-gradient(135deg, #6e8efb, #a777e3)';
    typeBtns[activeIndex].style.color = 'white';
    
    // UI要素の表示/非表示を切り替え
    if (type === 'navigation') {
        document.getElementById('moves').classList.remove('hidden');
        document.getElementById('guess-count').classList.add('hidden');
        document.getElementById('navigation-target').classList.remove('hidden');
        document.getElementById('guessing-target').classList.add('hidden');
        document.getElementById('answer-form').classList.add('hidden');
    } else {
        document.getElementById('moves').classList.add('hidden');
        document.getElementById('guess-count').classList.remove('hidden');
        document.getElementById('navigation-target').classList.add('hidden');
        document.getElementById('guessing-target').classList.remove('hidden');
        document.getElementById('answer-form').classList.remove('hidden');
    }
    
    // 現在のゲームが進行中なら再スタート
    if (currentPage) {
        startGame();
    }
}

// 回答をチェックする関数
function checkAnswer() {
    const userAnswer = document.getElementById('answer-input').value.trim();
    
    if (!userAnswer) return; // 空の回答はチェックしない
    
    guessCount++;
    updateStats();
    
    // 正解のページタイトルと比較（大文字小文字を区別しない）
    if (userAnswer.toLowerCase() === correctPageTitle.toLowerCase()) {
        // 正解した場合
        saveGameResult();
        showCompletionModal();
        // 入力フィールドをクリア
        document.getElementById('answer-input').value = '';
    } else {
        // 不正解の場合
        showWrongAnswerToast();
        // 入力フィールドを選択状態にして再入力しやすくする
        document.getElementById('answer-input').select();
    }
}

// 不正解時のトースト表示
function showWrongAnswerToast() {
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
    
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 2000);
}

        function hideCompletionModal() {
            document.getElementById('completion-modal').style.display = 'none';
        }

        function createConfetti() {
            const confettiCount = 100;
            const colors = ['#6e8efb', '#a777e3', '#ffcc00', '#ff7675', '#55efc4', '#00cec9'];
            // In singleplayer_game.js, the modal content ID is 'wikipedia-game-modal-content'
            const confettiContainer = document.getElementById('wikipedia-game-modal-content'); 

            if (!confettiContainer) {
                console.error('Confetti container (#wikipedia-game-modal-content) not found');
                return;
            }

            // Clear existing confetti from this specific container
            const existingConfetti = confettiContainer.querySelectorAll('.confetti');
            existingConfetti.forEach(c => c.remove());

            for (let i = 0; i < confettiCount; i++) {
                const confetti = document.createElement('div');
                confetti.className = 'confetti'; // Uses common styles from common_styles.css
                
                confetti.style.left = Math.random() * 100 + '%';
                confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
                const size = Math.random() * 8 + 4; // Standardized size randomization
                confetti.style.width = size + 'px';
                confetti.style.height = size * 1.5 + 'px';
                confetti.style.opacity = Math.random() * 0.6 + 0.4; // Standardized opacity

                confetti.style.animationName = 'common-confetti-fall';
                confetti.style.animationDuration = (Math.random() * 2 + 3) + 's'; 
                confetti.style.animationDelay = (Math.random() * 1.5) + 's'; 
                confetti.style.animationTimingFunction = 'ease-in'; 
                confetti.style.animationIterationCount = '1'; 
                confetti.style.animationFillMode = 'forwards'; 

                confettiContainer.appendChild(confetti);
            }
        }
        
        function getRatingMessage(moves) {
            if (moves <= 3) {
                return {
                    rating: "★★★★★",
                    message: "天才的！驚異的なナビゲーション能力です！"
                };
            } else if (moves <= 5) {
                return {
                    rating: "★★★★☆",
                    message: "素晴らしい！WikipediaのMVPですね！"
                };
            } else if (moves <= 8) {
                return {
                    rating: "★★★☆☆",
                    message: "良いナビゲーション！知識の海を泳ぎこなしました！"
                };
            } else if (moves <= 12) {
                return {
                    rating: "★★☆☆☆",
                    message: "よく頑張りました！次はもっと短い経路を探してみましょう。"
                };
            } else {
                return {
                    rating: "★☆☆☆☆",
                    message: "ゴールにたどり着きました！練習あるのみです。"
                };
            }
        }

        function showCompletionModal() {
            // 評価を設定
            const rating = getRatingMessage(moveCount);
            document.getElementById('performance-rating').textContent = rating.rating;
            document.getElementById('completion-message').textContent = rating.message;
            
            // モーダルの内容を更新
            document.getElementById('final-moves').textContent = moveCount;
            document.getElementById('start-page-name').textContent = decodeURIComponent(startUrl).split('/').pop();
            document.getElementById('final-target-page').textContent = decodeURIComponent(targetUrl).split('/').pop();

            // 履歴表示
            updateGameHistory();

            // 紙吹雪エフェクト作成
            createConfetti();

            // モーダル表示
            document.getElementById('completion-modal').style.display = 'flex';
            
            // 効果音を再生（オプション）
            try {
                const audio = new Audio('https://assets.mixkit.co/sfx/preview/mixkit-winning-chimes-2015.mp3');
                audio.volume = 0.5;
                audio.play();
            } catch (e) {
                console.error('効果音再生エラー:', e);
            }
        }

        function updateGameHistory() {
            const historyDiv = document.getElementById('game-history');
            historyDiv.innerHTML = '<h3>移動履歴</h3>';
            
            const historyList = document.createElement('ol');
            gamePath.forEach(page => {
                const item = document.createElement('li');
                item.textContent = decodeURIComponent(page).split('/').pop();
                historyList.appendChild(item);
            });
            
            historyDiv.appendChild(historyList);
        }

        function saveGameResult() {
            const result = {
                startPage: decodeURIComponent(startUrl).split('/').pop(),
                targetPage: decodeURIComponent(targetUrl).split('/').pop(),
                moves: moveCount,
                path: gamePath.map(url => decodeURIComponent(url).split('/').pop()),
                date: new Date().toLocaleString()
            };
            
            gameResults.push(result);
            
            // ローカルストレージに保存（オプション）
            try {
                localStorage.setItem('wikiGameResults', JSON.stringify(gameResults));
            } catch (e) {
                console.error('結果の保存に失敗:', e);
            }
            
            return result;
        }

        async function fetchRandomPage() {
            const response = await fetch('/api/random-page');
            const data = await response.json();
            return data.url;
        }

        async function fetchPageLinks(url) {
            try {
                const response = await fetch(`/api/page-links?url=${encodeURIComponent(url)}`);
                const data = await response.json();
                return data.links || [];
            } catch (error) {
                console.error('リンク取得エラー:', error);
                return [];
            }
        }

        async function startGame() {
            moveCount = 0;
            guessCount = 0;
            currentPage = '';
            gamePath = []; // 履歴をリセット
            hideCompletionModal(); // モーダルを非表示
            document.getElementById('answer-input').value = ''; // 回答フォームをクリア
            
            // ターゲットの再設定（固定）
            targetUrl = 'https://ja.wikipedia.org/wiki/日本';
            targetPath = '/wiki/日本';
            document.getElementById('target-page-name').textContent = '日本';
            updateStats();

            try {
                startUrl = await fetchRandomPage();
                currentPage = startUrl;
                gamePath.push(startUrl); // 開始ページを履歴に追加

                // ゲームモードに応じたパラメータ付きでプロキシURLを構築
                let frameUrl;
                if (gameType === 'guessing') {
                    frameUrl = `/proxy?url=${encodeURIComponent(startUrl)}&mode=guessing`;
                    // 回答対象のページタイトルを取得
                    correctPageTitle = decodeURIComponent(startUrl).split('/').pop().replace(/_/g, ' ');
                } else {
                    frameUrl = `/proxy?url=${encodeURIComponent(startUrl)}`;
                }
                
                document.getElementById('start-frame').src = frameUrl;

                availableLinks = await fetchPageLinks(startUrl);
                updateStats();
            } catch (error) {
                console.error('ゲーム開始エラー:', error);
                showToast('ゲームの開始に失敗しました。もう一度お試しください。', 'error');
            }
        }

        // URLがWikipediaの記事かどうかを確認する関数
        function isValidWikipediaArticle(url) {
            try {
                const urlObj = new URL(url);
                const path = urlObj.pathname;
                return path.startsWith('/wiki/') &&
                    !path.includes(':') &&
                    !path.includes('Special:') &&
                    !path.includes('Wikipedia:') &&
                    !path.includes('File:') &&
                    !path.includes('Template:');
            } catch (e) {
                return false;
            }
        }

        // イベントリスナーの設定
        document.getElementById('start-frame').addEventListener('load', function () {
            const frame = this;

            try {
                const frameDoc = frame.contentDocument || frame.contentWindow.document;

                // スクリプトを無効化
                const scripts = frameDoc.getElementsByTagName('script');
                Array.from(scripts).forEach(script => script.remove());

                // リンクにイベントリスナーを追加
                const links = frameDoc.getElementsByTagName('a');
                Array.from(links).forEach(link => {
                    link.addEventListener('click', async function (e) {
                        e.preventDefault();
                        const href = this.getAttribute('href');

                        if (href) {
                            let fullUrl;
                            if (href.startsWith('/wiki/')) {
                                // 相対パスの場合
                                fullUrl = `https://ja.wikipedia.org${href}`;
                            } else if (href.includes('wikipedia.org')) {
                                // 絶対パスの場合
                                fullUrl = href;
                            } else {
                                // その他のリンクは無視
                                return;
                            }

                            if (isValidWikipediaArticle(fullUrl)) {
                                await navigateToPage(fullUrl);
                            } else {
                                console.log('無効なWikipediaリンク:', fullUrl);
                            }
                        }
                    });
                });

                // スタイルの追加
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
                `;
                frameDoc.head.appendChild(style);

            } catch (e) {
                console.error('フレーム処理エラー:', e);
            }
        });

        // ページ遷移処理
        async function navigateToPage(clickedUrl) {
            try {
                // 新しいページのリンクを取得
                const newLinks = await fetchPageLinks(clickedUrl);

                moveCount++;
                currentPage = clickedUrl;
                gamePath.push(clickedUrl); // 移動先を履歴に追加
                availableLinks = newLinks;
                updateStats();

                // ゲームモードに応じて処理分岐
                if (gameType === 'guessing') {
                    // 新しいページタイトルを設定
                    correctPageTitle = decodeURIComponent(clickedUrl).split('/').pop().replace(/_/g, ' ');
                    
                    // フレームを更新（タイトル隠しモード）
                    const frameUrl = `/proxy?url=${encodeURIComponent(clickedUrl)}&mode=guessing`;
                    document.getElementById('start-frame').src = frameUrl;
                    
                    // 回答フォームをクリア
                    document.getElementById('answer-input').value = '';
                    
                    // 推測回数をリセット
                    guessCount = 0;
                    updateStats();
                } else {
                    // ナビゲーションモード
                    // フレームを通常モードで更新
                    const frameUrl = `/proxy?url=${encodeURIComponent(clickedUrl)}`;
                    document.getElementById('start-frame').src = frameUrl;

                    // サーバー側で目的のページに到達したかチェック
                    console.log('検証中:', clickedUrl, targetUrl);
                    
                    // サーバーAPIを呼び出して判定
                    fetch(`/api/check-target?current=${encodeURIComponent(clickedUrl)}&target=${encodeURIComponent(targetUrl)}`)
                        .then(response => response.json())
                        .then(data => {
                            console.log('目標チェック結果:', data);
                            
                            if (data.is_target) {
                                console.log('目標ページに到達しました！');
                                // ゲーム結果を保存
                                const gameResult = saveGameResult();
                                
                                // 結果モーダルを表示
                                showCompletionModal();
                            } else {
                                console.log('目標ではありません。継続します。');
                            }
                        })
                        .catch(error => {
                            console.error('目標チェックエラー:', error);
                        });
                }
            } catch (error) {
                console.error('ページ遷移エラー:', error);
                showToast('ページの遷移に失敗しました。', 'error');
            }
        }

        // ゲーム開始
        startGame();
        
        // ゲームモード切り替え
        function showSinglePlayer() {
            // シングルプレイヤーモードを表示（すでに表示されている）
            const modeBtns = document.querySelectorAll('.mode-btn');
            modeBtns.forEach(btn => btn.classList.remove('active'));
            modeBtns[0].classList.add('active');
            modeBtns[0].style.background = 'linear-gradient(135deg, #6e8efb, #a777e3)';
            modeBtns[0].style.color = 'white';
            modeBtns[1].style.background = '#f0f0f0';
            modeBtns[1].style.color = '#333';
        }
