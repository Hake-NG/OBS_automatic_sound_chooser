import time
import psutil
import win32gui
import win32process
from pycaw.pycaw import AudioUtilities
import obsws_python as obs

# ==========================================
# 1. КОНФИГУРАЦИЯ ДОРОЖЕК
# ==========================================
# Ключ словаря — это название категории (логическое имя).
# Внутри: 
#   'obs_source' - точное название источника "Захват звука приложения" в твоем OBS.
#   'processes' - список известных .exe файлов (классический метод).
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

# Настройки подключения к OBS
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "your_password" # Впиши свой пароль от WebSocket

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def get_window_title_by_pid(pid):
    """Находит заголовок видимого окна по ID процесса (PID)."""
    hwnds = []
    def callback(hwnd, hwnds):
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                hwnds.append(hwnd)
        return True
    
    win32gui.EnumWindows(callback, hwnds)
    
    if hwnds:
        # Возвращаем заголовок первого найденного окна
        return win32gui.GetWindowText(hwnds[0])
    return ""

def categorize_process(exe_name):
    """
    Определяет, к какой категории относится процесс.
    Именно ЗДЕСЬ в будущем можно подключить ИИ!
    Если .exe нет в наших списках, ИИ может проанализировать имя и вернуть категорию.
    """
    exe_name_lower = exe_name.lower()
    
    # 1. Сначала ищем по нашим жестким спискам
    for category, data in TRACK_CONFIG.items():
        if exe_name_lower in data["processes"]:
            return category
            
    # 2. МЕСТО ДЛЯ ИИ: 
    # Если процесс не найден (например, новая игра "unknown_game.exe"),
    # тут можно сделать запрос к локальной нейросети, которая вернет "Games".
    
    # Пока возвращаем None, если процесс нам неизвестен
    return None

# ==========================================
# 3. ОСНОВНАЯ ЛОГИКА
# ==========================================

def main():
    print("Подключение к OBS...")
    try:
        # Подключаемся к OBS
        cl = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
        print("Успешно подключено к OBS WebSocket!")
    except Exception as e:
        print(f"Ошибка подключения к OBS: {e}")
        return

    # Словарь для хранения текущих выставленных входов в OBS, 
    # чтобы не спамить командами каждую секунду, если ничего не изменилось.
    current_obs_state = {category: "" for category in TRACK_CONFIG.keys()}

    print("Начинаю мониторинг звука Windows...")

    while True:
        try:
            # Получаем все активные аудиосессии (процессы, которые сейчас "звучат")
            sessions = AudioUtilities.GetAllSessions()
            
            # Словарь: Категория -> Данные окна (exe и заголовок), которое сейчас выдает звук
            active_categories = {}

            for session in sessions:
                if session.Process:
                    exe_name = session.Process.name()
                    pid = session.Process.pid
                    
                    category = categorize_process(exe_name)
                    
                    # Если мы знаем категорию этого процесса и её еще нет в active_categories
                    # (берем первый попавшийся активный процесс в категории)
                    if category and category not in active_categories:
                        window_title = get_window_title_by_pid(pid)
                        if window_title:
                            active_categories[category] = {
                                "exe": exe_name,
                                "title": window_title
                            }

            # Теперь обновляем источники в OBS
            for category, data in TRACK_CONFIG.items():
                obs_source_name = data["obs_source"]
                
                # Если в этой категории сейчас кто-то издает звук
                if category in active_categories:
                    exe = active_categories[category]["exe"]
                    title = active_categories[category]["title"]
                    
                    # Формируем строку формата OBS: [Имя.exe]: Заголовок
                    obs_window_string = f"[{exe}]: {title}"
                    
                    # Если источник поменялся, отправляем команду в OBS
                    if current_obs_state[category] != obs_window_string:
                        print(f"[{category}] Смена источника: {obs_source_name} -> {obs_window_string}")
                        
                        try:
                            # Отправляем команду на смену окна
                            cl.set_input_settings(
                                name=obs_source_name, 
                                settings={"window": obs_window_string}, 
                                overlay=True
                            )
                            current_obs_state[category] = obs_window_string
                        except Exception as e:
                            print(f"Ошибка при смене источника {obs_source_name} в OBS: {e}")

        except Exception as e:
            print(f"Произошла ошибка в цикле: {e}")

        # Пауза перед следующей проверкой (в секундах)
        # 2 секунды - оптимально, чтобы не грузить процессор
        time.sleep(2)

if __name__ == "__main__":
    main()
