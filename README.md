# HotkeyTimer

[English](#english) | [中文](#中文)

---

## English

Looping countdown timers for Windows, triggered by global hotkeys. Handy for games and anything else with recurring cooldowns.

### Install & run

```
pip install -r requirements.txt
```

Double-click `start.bat` (no console window), or run `python hotkey_timer.py`.

### Usage

1. **Right-click** anywhere in the window → **+ Add timer**
2. Each timer has a **name**, **countdown seconds** and **trigger key**. Open its settings with the ⚙ icon, a double-click on the card, or the right-click menu
3. Press the trigger key (works in any window) → the countdown starts from the target seconds
4. When it reaches 0 → it restarts from the target automatically (one cycle is exactly the target seconds)
5. Press the trigger key again while running → it restarts from the target
6. Turns **yellow** at 10 seconds left and **red** at 5 seconds left. At the per-timer **alert time** (default 10 seconds left), a Chinese voice says "注意 [timer name]"
7. The right-click menu also has **Always on top** and **Opacity…** (a slider from 20% to 100%)
8. Stop: the ■ icon or the right-click menu. Delete: **Delete timer** in the settings dialog (asks for confirmation)
9. All settings, including always-on-top and opacity, are saved to `config.json` and loaded on the next start

### Notes

- Cards sit in a single row and scale with the window
- The number is always shown in plain seconds (e.g. 600)
- The alert time must be less than the countdown seconds. The voice alert can be turned off per timer
- The voice alert uses the built-in Windows speech engine and prefers a Chinese voice
- Typing in this app's input fields does not trigger timers
- Several timers can share one key; they all trigger together
- If a game running as administrator doesn't receive the hotkey here, run this app as administrator too

---

## 中文

Windows 用的全域快捷鍵循環倒數計時器，適合遊戲技能冷卻、BOSS 重生等需要重複計時的情境。

### 安裝與啟動

```
pip install -r requirements.txt
```

雙擊 `start.bat`（不會跳出命令列視窗），或執行 `python hotkey_timer.py`。

### 使用方式

1. 在視窗任意處按**滑鼠右鍵** →「+ Add timer」
2. 每個計時器可設定**名稱**、**倒數秒數**、**觸發按鍵**（卡片右上角 ⚙、雙擊卡片、或右鍵選單開啟設定）
3. 按下觸發按鍵（任何視窗下都有效）→ 從設定秒數開始倒數
4. 倒數到 0 → 自動從設定秒數重新開始（一輪剛好等於設定秒數）
5. 倒數中再按一次觸發按鍵 → 從設定秒數重新開始
6. 剩 10 秒變**黃色**、剩 5 秒變**紅色**；在設定的「提醒時間」（預設剩 10 秒，每個計時器可不同）以中文語音提醒「注意 [計時器名稱]」
7. 右鍵選單可切換「Always on top（視窗置頂）」，「Opacity…（透明度）」開啟滑桿調整（20%～100%）
8. 停止：卡片左上角 ■ 或右鍵選單；刪除：設定視窗內「Delete timer」（會再確認）
9. 所有設定（含置頂、透明度）自動儲存在 `config.json`，下次開啟會自動載入

### 備註

- 卡片排成一列，隨視窗大小等比例縮放
- 數字一律以秒數顯示（例如 600）
- 提醒時間需小於倒數秒數；語音提醒可在設定中關閉
- 語音使用 Windows 內建語音，優先選用中文語音
- 在本程式的輸入框打字時，不會觸發計時器
- 多個計時器可以設定同一個按鍵，會同時觸發
- 如果某些遊戲以系統管理員身分執行時偵測不到按鍵，請以系統管理員身分執行本程式
