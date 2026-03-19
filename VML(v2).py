import minecraft_launcher_lib
import subprocess
import os
import sys
import shutil
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import threading
import ctypes
import datetime
import time
import uuid
import platform
import logging
from PIL import Image, ImageTk

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

# Включаем поддержку высокого DPI для Windows
try:
    if platform.system() == "Windows":
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception as e:
    logging.debug(f"Не удалось установить DPI awareness: {e}")

def open_folder_crossplatform(path):
    """Кроссплатформенное открытие папки"""
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", path])
    else:  # Linux
        subprocess.run(["xdg-open", path])

class ConfigManager:
    """Класс для управления конфигурацией лаунчера"""
    def __init__(self, config_file):
        self.config_file = config_file
        self.data = {
            "minecraft_path": "",
            "java_args": "",
            "max_ram": 2048,
            "version_names": {},
            "usernames": ["Steve"]
        }
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    self.data.update(loaded_data)
            except Exception as e:
                logging.error(f"Ошибка загрузки конфига: {e}")

    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
            logging.info("Конфигурация сохранена")
        except Exception as e:
            logging.error(f"Ошибка сохранения конфига: {e}")

class MinecraftCore:
    """Класс для работы с ядром Minecraft (установка, запуск)"""
    def __init__(self, config_manager):
        self.config = config_manager
        self.process = None
        self.is_running = False

    @property
    def mc_dir(self):
        return self.config.data["minecraft_path"]

    def create_directories(self):
        if not self.mc_dir:
            return
        dirs = ["versions", "libraries", "assets", "logs", "screenshots", "crash-reports"]
        try:
            os.makedirs(self.mc_dir, exist_ok=True)
            for d in dirs:
                os.makedirs(os.path.join(self.mc_dir, d), exist_ok=True)
        except Exception as e:
            logging.error(f"Ошибка создания папок: {e}")

    def get_installed_versions(self):
        installed = []
        versions_dir = os.path.join(self.mc_dir, "versions")
        if os.path.exists(versions_dir):
            for item in os.listdir(versions_dir):
                item_path = os.path.join(versions_dir, item)
                if os.path.isdir(item_path):
                    json_path = os.path.join(item_path, f"{item}.json")
                    jar_path = os.path.join(item_path, f"{item}.jar")
                    if os.path.exists(json_path) and os.path.exists(jar_path):
                        installed.append(item)
        installed.sort()
        return installed

    def install_version(self, version):
        minecraft_launcher_lib.install.install_minecraft_version(version, self.mc_dir)

    def launch(self, version, username):
        if self.is_running:
            raise RuntimeError("Minecraft уже запущен")

        session_uuid = str(uuid.uuid4())
        max_ram = self.config.data["max_ram"]
        java_args = [f"-Xmx{max_ram}M", "-Xms512M"]
        
        custom_args = self.config.data.get("java_args", "").strip()
        if custom_args:
            java_args.extend(custom_args.split())

        options = {
            "username": username,
            "uuid": session_uuid,
            "token": "",
            "gameDirectory": self.mc_dir,
            "jvmArguments": java_args
        }

        cmd = minecraft_launcher_lib.command.get_minecraft_command(version, self.mc_dir, options)
        logs_dir = os.path.join(self.mc_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Добавляем аргумент логов
        try:
            java_idx = next(i for i, p in enumerate(cmd) if 'java' in p)
            mem_end = java_idx + 1
            while mem_end < len(cmd) and cmd[mem_end].startswith('-X'):
                mem_end += 1
            cmd = cmd[:mem_end] + [f"-Dminecraft.logs={logs_dir}"] + cmd[mem_end:]
        except StopIteration:
            pass # Если не нашли вызов java, оставляем как есть

        logging.info(f"Запуск {version} для {username}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
            cwd=self.mc_dir,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )
        self.is_running = True
        return self.process

class MinecraftLauncherGUI:
    """Класс графического интерфейса пользователя"""
    def __init__(self, root):
        self.root = root
        self.root.title("Minecraft Vanilla Launcher")
        self.root.geometry("1200x750")
        self.root.minsize(1000, 650)
        
        self.colors = {
            'bg': '#2b2b2b',
            'bg_light': '#3c3f41',
            'bg_lighter': '#4e5254',
            'fg': '#ffffff',
            'fg_secondary': '#888888',
            'accent': '#007acc',
            'accent_hover': '#1c97ea',
        }
        self.root.configure(bg=self.colors['bg'])
        
        # Инициализация менеджеров
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher_config.json")
        self.config_manager = ConfigManager(config_path)
        self.core = MinecraftCore(self.config_manager)
        
        self.selected_version = None
        self.username = tk.StringVar(value=self.config_manager.data["usernames"][0])
        
        # Переменные для скриншотов
        self.screenshots = []
        self.current_screenshot = 0
        self.current_photo = None # Защита от утечки памяти
        self.current_pil_image = None
        
        logging.info("Инициализация интерфейса")
        
        if not self.core.mc_dir:
            self.ask_for_directory()
        else:
            self.core.create_directories()
        
        self.setup_styles()
        self.create_widgets()
        self.refresh_versions()
        self.refresh_screenshots()
        self.center_window(self.root)

    def setup_styles(self):
        """Настройка стилей для ttk виджетов (вкладки, ползунки)"""
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background=self.colors['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', background=self.colors['bg_light'], 
                        foreground=self.colors['fg'], padding=[20, 10], 
                        font=("Segoe UI", 10), borderwidth=0)
        style.map('TNotebook.Tab', 
                  background=[('selected', self.colors['accent'])], 
                  foreground=[('selected', self.colors['fg'])])

    def center_window(self, window, width=None, height=None):
        window.update_idletasks()
        w = width or window.winfo_width()
        h = height or window.winfo_height()
        x = (window.winfo_screenwidth() - w) // 2
        y = (window.winfo_screenheight() - h) // 2
        window.geometry(f"+{x}+{y}")

    def _create_centered_dialog(self, title, width, height):
        """DRY: Вспомогательный метод для создания всплывающих окон"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry(f"{width}x{height}")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors['bg'])
        self.center_window(dialog, width, height)
        
        frame = tk.Frame(dialog, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        return dialog, frame

    def create_widgets(self):
        # Основной контейнер (Вкладки)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 0))
        
        self.main_frame = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.screenshots_frame = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.settings_frame = tk.Frame(self.notebook, bg=self.colors['bg'])
        
        self.notebook.add(self.main_frame, text="🏠 Главная")
        self.notebook.add(self.screenshots_frame, text="📸 Скриншоты")
        self.notebook.add(self.settings_frame, text="⚙️ Настройки")
        
        self.create_main_tab()
        self.create_screenshots_tab()
        self.create_settings_tab()
        self.create_bottom_bar()

    # --- ВКЛАДКА: ГЛАВНАЯ ---
    def create_main_tab(self):
        left_frame = tk.Frame(self.main_frame, bg=self.colors['bg'])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10), pady=10)
        
        tk.Label(left_frame, text="📋 Установленные версии:", font=("Segoe UI", 12, "bold"), 
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor=tk.W, pady=(0, 5))
        
        list_frame = tk.Frame(left_frame, bg=self.colors['bg_lighter'], bd=2, relief=tk.SOLID)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.colors['bg_light'], troughcolor=self.colors['bg'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.versions_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                          bg=self.colors['bg_light'], fg=self.colors['fg'],
                                          selectbackground=self.colors['accent'], bd=0, 
                                          highlightthickness=0, font=("Consolas", 11))
        self.versions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.versions_listbox.yview)
        self.versions_listbox.bind('<<ListboxSelect>>', self.on_version_select)
        
        right_frame = tk.Frame(self.main_frame, bg=self.colors['bg'], width=350)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, pady=10)
        right_frame.pack_propagate(False)
        
        info_card = tk.Frame(right_frame, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(info_card, text="ℹ️ Информация о версии", font=("Segoe UI", 12, "bold"), 
                 bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W, padx=15, pady=(10, 5))
        self.info_label = tk.Label(info_card, text="Версия не выбрана", bg=self.colors['bg_light'], 
                                   fg=self.colors['fg_secondary'], justify=tk.LEFT, font=("Segoe UI", 10))
        self.info_label.pack(anchor=tk.W, padx=15, pady=(0, 10))
        
        buttons_frame = tk.Frame(right_frame, bg=self.colors['bg'])
        buttons_frame.pack(fill=tk.X)
        
        btns = [
            ("🚀 Запустить", self.launch_version, self.colors['accent'], self.colors['accent_hover'], "bold"),
            ("📦 Установить версию", self.install_version_dialog, self.colors['bg_light'], self.colors['bg_lighter'], "normal"),
            ("✏️ Переименовать", self.rename_version_dialog, self.colors['bg_light'], self.colors['bg_lighter'], "normal"),
            ("🗑️ Удалить", self.delete_version, self.colors['bg_light'], self.colors['bg_lighter'], "normal"),
            ("🔄 Обновить список", self.refresh_versions, self.colors['bg_light'], self.colors['bg_lighter'], "normal")
        ]
        
        for text, cmd, bg, abg, weight in btns:
            tk.Button(buttons_frame, text=text, command=cmd, bg=bg, fg=self.colors['fg'],
                      activebackground=abg, bd=0 if weight=="bold" else 1, padx=20, pady=8, 
                      font=("Segoe UI", 10, weight)).pack(fill=tk.X, pady=2)

    # --- ВКЛАДКА: СКРИНШОТЫ ---
    def create_screenshots_tab(self):
        content = tk.Frame(self.screenshots_frame, bg=self.colors['bg'])
        content.pack(fill=tk.BOTH, expand=True, pady=10)
        
        left_panel = tk.Frame(content, bg=self.colors['bg'], width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        tk.Label(left_panel, text="Список скриншотов:", bg=self.colors['bg'], 
                 fg=self.colors['fg'], font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        
        list_frame = tk.Frame(left_panel, bg=self.colors['bg_lighter'], bd=2, relief=tk.SOLID)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.colors['bg_light'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.screenshots_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                             bg=self.colors['bg_light'], fg=self.colors['fg'],
                                             selectbackground=self.colors['accent'], bd=0, 
                                             highlightthickness=0, font=("Segoe UI", 10))
        self.screenshots_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.screenshots_listbox.yview)
        self.screenshots_listbox.bind('<<ListboxSelect>>', self.on_screenshot_select)
        
        tk.Button(left_panel, text="🔄 Обновить", command=self.refresh_screenshots,
                 bg=self.colors['bg_light'], fg=self.colors['fg'], bd=1, pady=5).pack(fill=tk.X, pady=5)
        
        right_panel = tk.Frame(content, bg=self.colors['bg'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.preview_frame = tk.Frame(right_panel, bg=self.colors['bg_lighter'], bd=2, relief=tk.SUNKEN)
        self.preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        self.screenshot_label = tk.Label(self.preview_frame, bg=self.colors['bg_lighter'])
        self.screenshot_label.pack(fill=tk.BOTH, expand=True)
        # Привязка ресайза окна для динамического изменения картинки
        self.preview_frame.bind('<Configure>', self.on_preview_resize)
        
        info_frame = tk.Frame(right_panel, bg=self.colors['bg'], height=40)
        info_frame.pack(fill=tk.X)
        info_frame.pack_propagate(False)
        
        self.screenshot_name_label = tk.Label(info_frame, text="Нет выбранного скриншота",
                                            bg=self.colors['bg'], fg=self.colors['fg_secondary'])
        self.screenshot_name_label.pack(side=tk.LEFT, padx=5)
        
        btn_frame = tk.Frame(info_frame, bg=self.colors['bg'])
        btn_frame.pack(side=tk.RIGHT)
        
        tk.Button(btn_frame, text="📂 Открыть папку", command=self.open_screenshots_folder,
                 bg=self.colors['bg_light'], fg=self.colors['fg'], bd=1, padx=10).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="🗑️ Удалить", command=self.delete_screenshot,
                 bg=self.colors['bg_light'], fg=self.colors['fg'], bd=1, padx=10).pack(side=tk.LEFT, padx=2)

    # --- ВКЛАДКА: НАСТРОЙКИ ---
    def create_settings_tab(self):
        card = tk.Frame(self.settings_frame, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        card.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tk.Label(card, text="⚙️ Настройки лаунчера", font=("Segoe UI", 14, "bold"), 
                 bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W, padx=20, pady=(15, 15))
        
        # Директория
        tk.Label(card, text="📁 Папка Minecraft:", font=("Segoe UI", 11, "bold"), 
                 bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W, padx=20)
        p_frame = tk.Frame(card, bg=self.colors['bg_light'])
        p_frame.pack(fill=tk.X, padx=20, pady=(5, 15))
        
        self.path_var = tk.StringVar(value=self.config_manager.data["minecraft_path"])
        tk.Entry(p_frame, textvariable=self.path_var, bg=self.colors['bg'], fg=self.colors['fg'],
                 insertbackground=self.colors['fg'], bd=2, font=("Segoe UI", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))
        tk.Button(p_frame, text="Обзор", command=self.browse_path, bg=self.colors['bg'], fg=self.colors['fg'], bd=2).pack(side=tk.RIGHT)
        
        # RAM
        tk.Label(card, text="💾 Выделенная память (RAM MB):", font=("Segoe UI", 11, "bold"), 
                 bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W, padx=20)
        r_frame = tk.Frame(card, bg=self.colors['bg_light'])
        r_frame.pack(fill=tk.X, padx=20, pady=(5, 15))
        
        self.ram_var = tk.IntVar(value=self.config_manager.data["max_ram"])
        self.ram_label = tk.Label(r_frame, text=f"{self.ram_var.get()} MB", bg=self.colors['bg_light'], 
                                  fg=self.colors['accent'], font=("Segoe UI", 11, "bold"))
        self.ram_label.pack(side=tk.RIGHT)
        
        ram_slider = ttk.Scale(r_frame, from_=512, to_=16384, orient=tk.HORIZONTAL, variable=self.ram_var, command=self.update_ram_label)
        ram_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Аргументы Java
        tk.Label(card, text="☕ Дополнительные аргументы Java:", font=("Segoe UI", 11, "bold"), 
                 bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W, padx=20)
        self.args_var = tk.StringVar(value=self.config_manager.data.get("java_args", ""))
        tk.Entry(card, textvariable=self.args_var, bg=self.colors['bg'], fg=self.colors['fg'],
                 insertbackground=self.colors['fg'], bd=2, font=("Segoe UI", 10)).pack(fill=tk.X, padx=20, pady=(5, 5), ipady=5)
        
        tk.Button(card, text="💾 Сохранить настройки", command=self.save_settings, bg=self.colors['accent'], 
                  fg=self.colors['fg'], bd=0, padx=30, pady=10, font=("Segoe UI", 11, "bold")).pack(pady=20)

    # --- НИЖНЯЯ ПАНЕЛЬ ---
    def create_bottom_bar(self):
        bottom_bar = tk.Frame(self.root, bg=self.colors['bg_light'], height=60)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_bar.pack_propagate(False)
        
        left_frame = tk.Frame(bottom_bar, bg=self.colors['bg_light'])
        left_frame.pack(side=tk.LEFT, padx=20, pady=10)
        tk.Label(left_frame, text="💾 RAM:", bg=self.colors['bg_light'], fg=self.colors['fg']).pack(side=tk.LEFT)
        self.bottom_ram_info = tk.Label(left_frame, text=f'{self.config_manager.data["max_ram"]} MB', 
                                        bg=self.colors['bg_light'], fg=self.colors['accent'], font=("Segoe UI", 12, "bold"))
        self.bottom_ram_info.pack(side=tk.LEFT, padx=5)
        
        right_frame = tk.Frame(bottom_bar, bg=self.colors['bg_light'])
        right_frame.pack(side=tk.RIGHT, padx=20, pady=10)
        tk.Label(right_frame, text="👤 Ник:", bg=self.colors['bg_light'], fg=self.colors['fg']).pack(side=tk.LEFT)
        
        self.username_combo = ttk.Combobox(right_frame, textvariable=self.username, 
                                          values=self.config_manager.data["usernames"], width=20)
        self.username_combo.pack(side=tk.LEFT, padx=8, ipady=2)
        tk.Button(right_frame, text="⚙️", command=self.manage_usernames_dialog, bg=self.colors['accent'], 
                  fg=self.colors['fg'], bd=0, padx=10).pack(side=tk.LEFT)

    # --- ЛОГИКА GUI ---
    def browse_path(self):
        path = filedialog.askdirectory(title="Выберите папку Minecraft")
        if path:
            self.path_var.set(path)

    def update_ram_label(self, val):
        val = int(float(val))
        self.ram_label.config(text=f"{val} MB")

    def save_settings(self):
        old_path = self.config_manager.data["minecraft_path"]
        new_path = self.path_var.get().strip()
        
        self.config_manager.data["minecraft_path"] = new_path
        self.config_manager.data["max_ram"] = self.ram_var.get()
        self.config_manager.data["java_args"] = self.args_var.get().strip()
        self.config_manager.save()
        
        self.bottom_ram_info.config(text=f'{self.ram_var.get()} MB')
        
        if old_path != new_path:
            self.core.create_directories()
            self.refresh_versions()
            self.refresh_screenshots()
            
        messagebox.showinfo("Успех", "Настройки сохранены")

    def refresh_versions(self):
        self.versions_listbox.delete(0, tk.END)
        installed = self.core.get_installed_versions()
        names = self.config_manager.data.get("version_names", {})
        
        for v in installed:
            display = names.get(v, v)
            self.versions_listbox.insert(tk.END, f"  {display}")
            
        self.installed_versions_cache = installed

    def on_version_select(self, event):
        selection = self.versions_listbox.curselection()
        if selection:
            idx = selection[0]
            self.selected_version = self.installed_versions_cache[idx]
            display = self.config_manager.data["version_names"].get(self.selected_version, self.selected_version)
            
            # Подсчет размера (упрощенный)
            version_dir = Path(self.core.mc_dir) / "versions" / self.selected_version
            size_mb = sum(f.stat().st_size for f in version_dir.rglob('*') if f.is_file()) / (1024 * 1024) if version_dir.exists() else 0
            
            self.info_label.config(text=f"📝 Название: {display}\n📁 Версия: {self.selected_version}\n💾 Размер: {size_mb:.1f} MB")

    def launch_version(self):
        if not self.selected_version:
            messagebox.showwarning("Предупреждение", "Выберите версию")
            return
        try:
            process = self.core.launch(self.selected_version, self.username.get().strip() or "Steve")
            
            def monitor():
                process.wait()
                self.core.is_running = False
                logging.info("Minecraft закрыт")
                
            threading.Thread(target=monitor, daemon=True).start()
            messagebox.showinfo("Запуск", f"Запускаем {self.selected_version}...")
        except Exception as e:
            logging.error(f"Ошибка запуска: {e}")
            messagebox.showerror("Ошибка", str(e))

    def ask_for_directory(self):
        dialog, frame = self._create_centered_dialog("Первый запуск", 600, 250)
        content = tk.Frame(frame, bg=self.colors['bg_light'])
        content.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(content, text="Добро пожаловать!\nВыберите папку для Minecraft:", 
                 font=("Segoe UI", 12), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(pady=(0, 15))
        
        path_var = tk.StringVar(value=f"C:\\Users\\{os.getlogin()}\\Desktop\\Minecraft" if platform.system() == "Windows" else f"{Path.home()}/Minecraft")
        entry_frame = tk.Frame(content, bg=self.colors['bg_light'])
        entry_frame.pack(fill=tk.X)
        tk.Entry(entry_frame, textvariable=path_var, font=("Segoe UI", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        tk.Button(entry_frame, text="Обзор", command=lambda: path_var.set(filedialog.askdirectory() or path_var.get())).pack(side=tk.RIGHT, padx=5)
        
        def save():
            self.config_manager.data["minecraft_path"] = path_var.get().strip()
            self.config_manager.save()
            dialog.destroy()
            
        tk.Button(content, text="Сохранить", command=save, bg=self.colors['accent'], fg=self.colors['fg'], pady=8).pack(pady=20)
        self.root.wait_window(dialog)

    def install_version_dialog(self):
        dialog, frame = self._create_centered_dialog("Установка", 450, 250)
        
        tk.Label(frame, text="Версия:", bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W)
        ver_var = tk.StringVar()
        tk.Entry(frame, textvariable=ver_var).pack(fill=tk.X, pady=5, ipady=5)
        
        progress = ttk.Progressbar(frame, mode='indeterminate')
        status = tk.Label(frame, text="", bg=self.colors['bg_light'], fg=self.colors['fg_secondary'])
        
        def start():
            v = ver_var.get().strip()
            if not v: return
            progress.pack(fill=tk.X, pady=10)
            status.pack()
            progress.start()
            status.config(text="Загрузка файлов (это может занять время)...")
            
            def task():
                try:
                    self.core.install_version(v)
                    dialog.after(0, lambda: messagebox.showinfo("Готово", f"Версия {v} установлена"))
                    dialog.after(0, dialog.destroy)
                    dialog.after(0, self.refresh_versions)
                except Exception as e:
                    logging.error(f"Ошибка установки: {e}")
                    dialog.after(0, lambda: status.config(text="Ошибка установки!"))
                    dialog.after(0, progress.stop)
            threading.Thread(target=task, daemon=True).start()
            
        tk.Button(frame, text="Установить", command=start, bg=self.colors['accent'], fg=self.colors['fg']).pack(pady=15)

    def rename_version_dialog(self):
        if not self.selected_version: return
        dialog, frame = self._create_centered_dialog("Переименовать", 400, 180)
        
        tk.Label(frame, text=f"Новое имя для {self.selected_version}:", bg=self.colors['bg_light'], fg=self.colors['fg']).pack()
        name_var = tk.StringVar(value=self.config_manager.data["version_names"].get(self.selected_version, ""))
        tk.Entry(frame, textvariable=name_var).pack(fill=tk.X, pady=10, ipady=5)
        
        def save():
            n = name_var.get().strip()
            if n:
                self.config_manager.data["version_names"][self.selected_version] = n
            else:
                self.config_manager.data["version_names"].pop(self.selected_version, None)
            self.config_manager.save()
            self.refresh_versions()
            dialog.destroy()
            
        tk.Button(frame, text="Сохранить", command=save, bg=self.colors['accent'], fg=self.colors['fg']).pack()

    def delete_version(self):
        if not self.selected_version: return
        if messagebox.askyesno("Удаление", f"Удалить {self.selected_version}?"):
            try:
                shutil.rmtree(os.path.join(self.core.mc_dir, "versions", self.selected_version))
                self.config_manager.data["version_names"].pop(self.selected_version, None)
                self.config_manager.save()
                self.selected_version = None
                self.refresh_versions()
            except Exception as e:
                logging.error(f"Ошибка удаления: {e}")

    def manage_usernames_dialog(self):
        dialog, frame = self._create_centered_dialog("Ники", 400, 300)
        
        listbox = tk.Listbox(frame, bg=self.colors['bg'], fg=self.colors['fg'])
        listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        for n in self.config_manager.data["usernames"]: listbox.insert(tk.END, n)
        
        new_var = tk.StringVar()
        entry_frame = tk.Frame(frame, bg=self.colors['bg_light'])
        entry_frame.pack(fill=tk.X)
        tk.Entry(entry_frame, textvariable=new_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def add():
            n = new_var.get().strip()
            if n and n not in self.config_manager.data["usernames"]:
                self.config_manager.data["usernames"].append(n)
                self.config_manager.save()
                listbox.insert(tk.END, n)
                self.username_combo['values'] = self.config_manager.data["usernames"]
                new_var.set("")
                
        def delete():
            sel = listbox.curselection()
            if sel and len(self.config_manager.data["usernames"]) > 1:
                n = listbox.get(sel[0])
                self.config_manager.data["usernames"].remove(n)
                self.config_manager.save()
                listbox.delete(sel[0])
                self.username_combo['values'] = self.config_manager.data["usernames"]
                if self.username.get() == n: self.username.set(self.config_manager.data["usernames"][0])
                
        tk.Button(entry_frame, text="➕", command=add).pack(side=tk.RIGHT)
        tk.Button(frame, text="Удалить выбранный", command=delete).pack(fill=tk.X, pady=5)

    # --- ЛОГИКА СКРИНШОТОВ ---
    def refresh_screenshots(self):
        self.screenshots.clear()
        self.screenshots_listbox.delete(0, tk.END)
        ss_dir = os.path.join(self.core.mc_dir, "screenshots")
        
        if os.path.exists(ss_dir):
            files = [f for f in os.listdir(ss_dir) if f.lower().endswith(('.png', '.jpg'))]
            files.sort(reverse=True)
            self.screenshots = files
            for f in files:
                self.screenshots_listbox.insert(tk.END, f"  {f[:27] + '...' if len(f)>30 else f}")
        
        if not self.screenshots:
            self.screenshots_listbox.insert(tk.END, "  Нет скриншотов")

    def on_screenshot_select(self, event):
        sel = self.screenshots_listbox.curselection()
        if sel and self.screenshots:
            idx = sel[0]
            if idx < len(self.screenshots):
                filename = self.screenshots[idx]
                self.screenshot_name_label.config(text=f"Выбран: {filename}")
                self._load_screenshot(filename)

    def _load_screenshot(self, filename):
        filepath = os.path.join(self.core.mc_dir, "screenshots", filename)
        if not os.path.exists(filepath): return
        
        try:
            self.current_pil_image = Image.open(filepath)
            self._render_screenshot()
        except Exception as e:
            logging.error(f"Ошибка загрузки картинки: {e}")

    def _render_screenshot(self):
        """Отрисовка картинки с подгоном под размер фрейма"""
        if not self.current_pil_image: return
        
        pw = self.preview_frame.winfo_width()
        ph = self.preview_frame.winfo_height()
        if pw < 10 or ph < 10: return # Окно еще не отрисовалось
        
        iw, ih = self.current_pil_image.size
        scale = min(pw/iw, ph/ih, 1.0)
        
        if scale < 1.0:
            nw, nh = int(iw * scale), int(ih * scale)
            resized = self.current_pil_image.resize((nw, nh), Image.Resampling.LANCZOS)
        else:
            resized = self.current_pil_image
            
        # Устранение утечки: перезаписываем единственную ссылку
        self.current_photo = ImageTk.PhotoImage(resized)
        self.screenshot_label.config(image=self.current_photo)

    def on_preview_resize(self, event):
        """Динамическое изменение размера скриншота при ресайзе окна"""
        # Простая реализация. Для идеальной плавности нужен таймер-дебаунсер
        if self.current_pil_image:
            self._render_screenshot()

    def open_screenshots_folder(self):
        ss_dir = os.path.join(self.core.mc_dir, "screenshots")
        if os.path.exists(ss_dir):
            open_folder_crossplatform(ss_dir)
            
    def delete_screenshot(self):
        sel = self.screenshots_listbox.curselection()
        if not sel or not self.screenshots: return
        
        filename = self.screenshots[sel[0]]
        if messagebox.askyesno("Удаление", f"Удалить {filename}?"):
            try:
                os.remove(os.path.join(self.core.mc_dir, "screenshots", filename))
                self.screenshot_label.config(image='')
                self.current_photo = None
                self.current_pil_image = None
                self.refresh_screenshots()
            except Exception as e:
                logging.error(f"Ошибка удаления скриншота: {e}")

def main():
    root = tk.Tk()
    app = MinecraftLauncherGUI(root)
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}", exc_info=True)
        input("Нажмите Enter для выхода...")