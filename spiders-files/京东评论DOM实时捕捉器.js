// ==UserScript==
// @name         京东评论DOM实时捕捉器
// @namespace    http://tampermonkey.net/
// @version      2.1
// @description  1. 彻底拦截图片 2. 自动持久化存储 3. 修复悬浮窗显示问题
// @author       Gemini
// @match        *://item.jd.com/*
// @match        *://club.jd.com/*
// @grant        GM_addStyle
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    // --- 1. 图片强力拦截 (必须在 document-start 执行) ---
    GM_addStyle(`
        img, [style*="background-image"], video, canvas {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
        }
    `);

    // 拦截动态创建的图片
    const blocker = new MutationObserver((mutations) => {
        for (let m of mutations) {
            m.addedNodes.forEach(node => {
                if (node.tagName === 'IMG') node.src = '';
                if (node.querySelectorAll) {
                    node.querySelectorAll('img').forEach(i => i.src = '');
                }
            });
        }
    });
    blocker.observe(document.documentElement, { childList: true, subtree: true });

    // --- 2. 数据处理逻辑 ---
    const STORAGE_KEY = 'jd_comments_data_v1';
    let capturedData = new Map();

    // 从本地读取旧数据
    const loadData = () => {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                const obj = JSON.parse(saved);
                capturedData = new Map(Object.entries(obj));
            } catch (e) { console.error("读取缓存失败"); }
        }
    };
    loadData();

    const saveData = () => {
        const obj = Object.fromEntries(capturedData);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
    };

    function parseComment(el) {
        const index = el.getAttribute('data-index');
        if (!index || capturedData.has(index)) return;

        try {
            const item = {
                "id": index,
                "content": el.querySelector('.jdc-pc-rate-card-main-desc')?.innerText.trim() || "",
                "date": el.querySelector('.date.list')?.innerText.trim() || "",
                "sku": el.querySelector('.info')?.innerText.trim() || "",
                "images": Array.from(el.querySelectorAll('.jdc-image img')).map(img =>
                    (img.getAttribute('data-src') || img.src || "").replace('s300x300_', 's1080x1080_')
                )
            };
            capturedData.set(index, item);
            saveData();
            updateUI();
        } catch (e) {}
    }

    // --- 3. UI 挂载逻辑 (修复点：循环检测 body 是否准备好) ---
    function initUI() {
        if (!document.body) {
            setTimeout(initUI, 100); // 如果 body 还没出来，过 100ms 再试
            return;
        }

        if (document.getElementById('jd-collector-ui')) return; // 防止重复创建

        GM_addStyle(`
            #jd-collector-ui {
                position: fixed; top: 50px; left: 20px; z-index: 2147483647;
                background: #1a1a1a; color: #00ff00; padding: 15px;
                border-radius: 8px; border: 1px solid #333;
                box-shadow: 0 0 15px rgba(0,255,0,0.2);
                font-family: "Microsoft YaHei", sans-serif; min-width: 150px;
            }
            .jd-stat { font-size: 12px; margin-bottom: 8px; color: #aaa; }
            .jd-num { font-size: 28px; font-weight: bold; display: block; margin: 5px 0; }
            .jd-btn-group { display: flex; flex-direction: column; gap: 8px; }
            .jd-btn {
                cursor: pointer; border: none; padding: 8px;
                border-radius: 4px; font-size: 13px; transition: 0.2s;
                text-align: center; font-weight: bold;
            }
            #btn-dl { background: #0081ff; color: white; }
            #btn-dl:hover { background: #0070dd; }
            #btn-cls { background: #444; color: #eee; }
            #btn-cls:hover { background: #666; }
        `);

        const panel = document.createElement('div');
        panel.id = 'jd-collector-ui';
        panel.innerHTML = `
            <div class="jd-stat">已收集评论记录</div>
            <span class="jd-num" id="jd-count-display">0</span>
            <div class="jd-btn-group">
                <button id="btn-dl" class="jd-btn">导出 JSON 数据</button>
                <button id="btn-cls" class="jd-btn">清空当前缓存</button>
            </div>
        `;
        document.body.appendChild(panel);

        // 绑定事件
        document.getElementById('btn-dl').onclick = () => {
            const dataArray = Array.from(capturedData.values());
            const blob = new Blob([JSON.stringify(dataArray, null, 4)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `JD_Comments_${Date.now()}.json`;
            a.click();
        };

        document.getElementById('btn-cls').onclick = () => {
            if (confirm("确定清空已收集的 " + capturedData.size + " 条数据吗？")) {
                localStorage.removeItem(STORAGE_KEY);
                capturedData.clear();
                updateUI();
            }
        };

        updateUI();

        // UI 加载后开始监听 DOM 变化
        const domObserver = new MutationObserver(() => {
            document.querySelectorAll('div[data-index]').forEach(parseComment);
        });
        domObserver.observe(document.body, { childList: true, subtree: true });
    }

    function updateUI() {
        const el = document.getElementById('jd-count-display');
        if (el) el.innerText = capturedData.size;
    }

    // 启动 UI 初始化程序
    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', initUI);
    } else {
        initUI();
    }

})();