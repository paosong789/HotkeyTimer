# HotkeyTimer

[English](#english) | [中文](#中文)

---

## English

Looping countdown timers for Windows and macOS, triggered by global hotkeys. Handy for games and anything else with recurring cooldowns.

### Download

Get the latest version from **Releases** (right side of the repo page):

| File | For |
|---|---|
| `HotkeyTimer.exe` | Windows |
| `HotkeyTimer-mac-arm64.zip` | Mac with Apple Silicon (M1/M2/M3/M4) |
| `HotkeyTimer-mac-intel.zip` | Mac with Intel CPU |

**Windows first run:** if "Windows protected your PC" appears, click **More info → Run anyway**.

**macOS first run:**
1. Unzip and move `HotkeyTimer.app` to **Applications**
2. Open it. If macOS blocks it, go to **System Settings → Privacy & Security** and click **Open Anyway**. If it says the app "is damaged", run this in Terminal: `xattr -dr com.apple.quarantine /Applications/HotkeyTimer.app`
3. Allow **HotkeyTimer** under **System Settings → Privacy & Security → Input Monitoring** and **Accessibility**, then restart the app. Without this, hotkeys are not detected

### Run from source

```
pip install -r requirements.txt
python hotkey_timer.py
```

On Windows you can also double-click `start.bat` (no console window).

### Build

- Windows: double-click `build.bat` → `dist\HotkeyTimer.exe`
- macOS: `sh build_mac.sh` → `dist/HotkeyTimer-mac-<arch>.zip` (needs the python.org Python, which includes Tk)
- Automatic: push a tag such as `v1.1.0` and GitHub Actions builds both versions and publishes a Release

### Usage

1. **Right-click** anywhere in the window → **+ Add timer** (on Mac: two-finger click or Control-click)
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
- The voice alert uses the built-in system voice (Windows SAPI / macOS `say`) and prefers a Chinese voice
- Settings file: next to the exe on Windows; `~/Library/Application Support/HotkeyTimer/config.json` on macOS
- Typing in this app's input fields does not trigger timers
- Several timers can share one key; they all trigger together
- If a game running as administrator doesn't receive the hotkey here, run this app as administrator too

---

## 中文

Windows / macOS 用的全域快捷鍵循環倒數計時器，適合遊戲技能冷卻、BOSS 重生等需要重複計時的情境。

### 下載

到 repo 頁面右側的 **Releases** 下載最新版本：

| 檔案 | 適用 |
|---|---|
| `HotkeyTimer.exe` | Windows |
| `HotkeyTimer-mac-arm64.zip` | Apple 晶片 Mac（M1/M2/M3/M4） |
| `HotkeyTimer-mac-intel.zip` | Intel 晶片 Mac |

**Windows 首次執行：** 若出現「Windows 已保護您的電腦」，請點「其他資訊 → 仍要執行」。

**macOS 首次執行：**
1. 解壓縮後把 `HotkeyTimer.app` 移到「應用程式」資料夾
2. 開啟程式。若被系統阻擋，到「系統設定 → 隱私權與安全性」點「強制打開」；若顯示「已損毀」，請在終端機執行：`xattr -dr com.apple.quarantine /Applications/HotkeyTimer.app`
3. 到「系統設定 → 隱私權與安全性 →**輸入監控**」與「**輔助使用**」允許 HotkeyTimer，然後重新開啟程式。沒有開啟權限的話偵測不到按鍵

### 從原始碼執行

```
pip install -r requirements.txt
python hotkey_timer.py
```

Windows 也可以雙擊 `start.bat`（不會跳出命令列視窗）。

### 打包

- Windows：雙擊 `build.bat` → `dist\HotkeyTimer.exe`
- macOS：`sh build_mac.sh` → `dist/HotkeyTimer-mac-<arch>.zip`（需使用 python.org 版 Python，內含 Tk）
- 自動打包：推送 `v1.1.0` 這類 tag，GitHub Actions 會自動打包兩個版本並發布 Release

### 使用方式

1. 在視窗任意處按**滑鼠右鍵** →「+ Add timer」（Mac：觸控板雙指點按或 Control + 點擊）
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
- 語音使用系統內建語音（Windows SAPI / macOS `say`），優先選用中文語音
- 設定檔位置：Windows 在 exe 旁邊；macOS 在 `~/Library/Application Support/HotkeyTimer/config.json`
- 在本程式的輸入框打字時，不會觸發計時器
- 多個計時器可以設定同一個按鍵，會同時觸發
- 如果某些遊戲以系統管理員身分執行時偵測不到按鍵，請以系統管理員身分執行本程式
