import time
import psutil
import win32gui
import win32process
import os
import json
from pycaw.pycaw import AudioUtilities
import obsws_python as obs
import google.generativeai as genai

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
CACHE_FILE = "ai_cache.json"

TRACK_CONFIG = {
    "Games": {
        "obs_source": "Audio_Games",
        "processes": ["dota2.exe", "cs2.exe", "helldivers2.exe", "cyberpunk2077.exe"]
    },
    "Media": {
        "obs_source": "Audio_Music",
        "processes": ["spotify.exe", "vlc.exe"]
    },
    "Browser": {
        "obs_source": "Audio_Browser",
        "processes": ["chrome.exe", "firefox.exe", "msedge.exe", "opera.exe"]
    },
    "Discord": {
        "obs_source": "Audio_Discord",
        "processes": ["discord.exe"]
    }
}

# Настройки API и OBS
genai.configure(api_key="ТВОЙ_API_КЛЮЧ") 
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "your_password" 

model = genai.GenerativeModel('gemini-1.5-flash')
AVAILABLE_CATEGORIES = list(TRACK_CONFIG.keys())

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения кэша: {e}")

# Инициализируем кэш
ai_cache = load_cache()

def get_window_title_by_pid(pid):
    hwnds = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                hwnds.append(hwnd)
        return True
    
    try:
        win32gui.EnumWindows(callback, None)
        return win32gui.GetWindowText(hwnds[0]) if hwnds else ""
    except Exception:
        return ""

def categorize_process(exe_name):
    exe_name_lower = exe_name.lower()
    
    # 1. Проверка в конфиге
    for category, data in TRACK_CONFIG.items():
        if exe_name_lower in [proc.lower() for proc in data["processes"]]:
            return category
            
    # 2. Проверка в кэше
    if exe_name_lower in ai_cache:
        return ai_cache[exe_name_lower]
        
    # 3. Запрос к ИИ
    print(f"[AI] Анализирую новый процесс: {exe_name}...")
    prompt = f"""
    Классифицируй процесс Windows "{exe_name}" по категориям: {AVAILABLE_CATEGORIES}.
    Если это системный процесс или ты не уверен, ответь "None".
    Ответ строго одним словом.
    """
    
    try:
        response = model.generate_content(prompt)
        ai_answer = response.text.strip()
        
        result = ai_answer if ai_answer in AVAILABLE_CATEGORIES else None
        ai_cache[exe_name_lower] = result
        save_cache(ai_cache)
        return result
    except Exception as e:
        print(f"[AI ОШИБКА]: {e}")
        return None

# ==========================================
# 3. ОСНОВНАЯ ЛОГИКА
# ==========================================

def main():
    print("Подключение к OBS...")
    try:
        cl = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
        print("Успешно подключено к OBS!")
    except Exception as e:
        print(f"Ошибка подключения к OBS: {e}")
        return

    current_obs_state = {category: "" for category in TRACK_CONFIG.keys()}

    while True:
        try:
            sessions = AudioUtilities.GetAllSessions()
            active_categories = {}

            for session in sessions:
                if session.Process and session.Process.is_running():
                    try:
                        exe_name = session.Process.name()
                        pid = session.Process.pid
                        
                        category = categorize_process(exe_name)
                        
                        if category and category not in active_categories:
                            title = get_window_title_by_pid(pid)
                            if title:
                                active_categories[category] = {"exe": exe_name, "title": title}
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            for category, data in TRACK_CONFIG.items():
                source_name = data["obs_source"]
                
                if category in active_categories:
                    exe = active_categories[category]["exe"]
                    title = active_categories[category]["title"]
                    # Формат, который обычно ожидает OBS для Application Audio Capture
                    obs_window_string = f"{title}:{exe}:" 
                    
                    if current_obs_state[category] != obs_window_string:
                        print(f"[{category}] Обновление: {obs_window_string}")
                        try:
                            cl.set_input_settings(
                                name=source_name,
                                settings={"window": obs_window_string},
                                overlay=True
                            )
                            current_obs_state[category] = obs_window_string
                        except Exception as e:
                            print(f"Ошибка OBS: {e}")

        except Exception as e:
            print(f"Ошибка цикла: {e}")

        time.sleep(2)

if __name__ == "__main__":
    main()
