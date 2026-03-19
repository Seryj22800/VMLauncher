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
from PIL import Image, ImageTk

# Включаем поддержку высокого DPI для Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

class MinecraftLauncherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Minecraft Vanilla Launcher")
        
        # Устанавливаем размер окна
        self.root.geometry("1200x750")
        self.root.minsize(1000, 650)
        self.root.resizable(True, True)
        
        # Цвета темы
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
        
        # Путь к конфигурационному файлу
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher_config.json")
        
        # Загружаем настройки
        self.config = self.load_config()
        
        # Основные переменные
        self.minecraft_directory = self.config.get("minecraft_path", "")
        self.java_args = self.config.get("java_args", "")
        self.max_ram = self.config.get("max_ram", 2048)
        self.min_ram = 0
        self.version_names = self.config.get("version_names", {})
        self.installed_versions = []
        self.selected_version = None
        
        # Ники игроков
        self.usernames = self.config.get("usernames", ["Steve"])
        if not self.usernames:
            self.usernames = ["Steve"]
        self.username = tk.StringVar(value=self.usernames[0])
        
        # Генерируем UUID для текущего пользователя
        self.user_uuid = self.generate_uuid()
        
        # Переменные для процесса Minecraft
        self.minecraft_process = None
        self.minecraft_running = False
        
        # Переменные для скриншотов
        self.screenshots = []
        self.current_screenshot = 0
        self.photo_images = []
        self.screenshot_label_display = None
        self.screenshot_name_label = None
        
        # Переменные для прогресса установки
        self.install_progress = 0
        self.install_status = ""
        
        # Логирование
        self.log("Лаунчер запущен", "INFO")
        
        # Проверка первого запуска
        self.is_first_launch = not self.minecraft_directory
        if self.is_first_launch:
            self.ask_for_directory()
        else:
            self.log(f"Папка Minecraft: {self.minecraft_directory}", "INFO")
            self.create_directories()
        
        # Создаём интерфейс
        self.create_widgets()
        
        # Обновляем список версий
        self.refresh_versions()
        
        # Обновляем список скриншотов
        self.refresh_screenshots()
        
        # Центрируем окно
        self.center_window()
    
    def generate_uuid(self):
        """Генерация UUID для пользователя"""
        return str(uuid.uuid4())
    
    def log(self, message, level="INFO"):
        """Логирование в консоль"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def get_available_versions(self):
        """Список доступных версий Minecraft"""
        try:
            version_manifest = minecraft_launcher_lib.utils.get_version_list()
            return [v["id"] for v in version_manifest]
        except Exception as e:
            self.log(f"Ошибка получения списка версий: {e}", "ERROR")
            return []
    
    def load_config(self):
        """Загрузка конфига"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_config(self):
        """Сохранение конфига"""
        self.config["minecraft_path"] = self.minecraft_directory
        self.config["version_names"] = self.version_names
        self.config["java_args"] = self.java_args
        self.config["max_ram"] = self.max_ram
        self.config["usernames"] = self.usernames
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            self.log("Конфигурация сохранена", "INFO")
        except Exception as e:
            self.log(f"Ошибка сохранения: {e}", "ERROR")
    
    def create_directories(self):
        """Создание папок"""
        try:
            os.makedirs(self.minecraft_directory, exist_ok=True)
            os.makedirs(os.path.join(self.minecraft_directory, "versions"), exist_ok=True)
            os.makedirs(os.path.join(self.minecraft_directory, "libraries"), exist_ok=True)
            os.makedirs(os.path.join(self.minecraft_directory, "assets"), exist_ok=True)
            os.makedirs(os.path.join(self.minecraft_directory, "logs"), exist_ok=True)
            os.makedirs(os.path.join(self.minecraft_directory, "screenshots"), exist_ok=True)
            os.makedirs(os.path.join(self.minecraft_directory, "crash-reports"), exist_ok=True)
        except Exception as e:
            self.log(f"Ошибка создания папок: {e}", "ERROR")
    
    def ask_for_directory(self):
        """Диалог выбора папки при первом запуске"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Первый запуск")
        dialog.geometry("600x300")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors['bg'])
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 600) // 2
        y = (dialog.winfo_screenheight() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        
        frame = tk.Frame(dialog, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        content = tk.Frame(frame, bg=self.colors['bg_light'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(content, text="Добро пожаловать!", 
                font=("Segoe UI", 16, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(pady=(0, 15))
        
        tk.Label(content, text="Выберите папку для Minecraft:", 
                bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W)
        
        path_frame = tk.Frame(content, bg=self.colors['bg_light'])
        path_frame.pack(fill=tk.X, pady=10)
        
        path_var = tk.StringVar(value=f"C:\\Users\\{os.getlogin()}\\Desktop\\Minecraft")
        entry = tk.Entry(path_frame, textvariable=path_var, 
                        bg=self.colors['bg'], fg=self.colors['fg'], bd=2,
                        font=("Segoe UI", 10))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))
        
        def browse():
            path = filedialog.askdirectory()
            if path:
                path_var.set(path)
        
        tk.Button(path_frame, text="Обзор", command=browse,
                 bg=self.colors['bg'], fg=self.colors['fg'],
                 bd=2, padx=10, pady=2).pack(side=tk.RIGHT)
        
        def save():
            path = path_var.get().strip()
            if path:
                self.minecraft_directory = path
                self.create_directories()
                self.save_config()
                dialog.destroy()
        
        btn_frame = tk.Frame(content, bg=self.colors['bg_light'])
        btn_frame.pack(fill=tk.X, pady=15)
        
        tk.Button(btn_frame, text="Сохранить", command=save,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 bd=0, padx=30, pady=8, font=("Segoe UI", 10, "bold")).pack()
        
        self.root.wait_window(dialog)
    
    def center_window(self):
        """Центрирование главного окна"""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Создание интерфейса"""
        # Верхняя панель с вкладками
        self.tab_bar = tk.Frame(self.root, bg=self.colors['bg_light'], height=40)
        self.tab_bar.pack(fill=tk.X)
        self.tab_bar.pack_propagate(False)
        
        # Вкладки
        self.tab_main = tk.Button(self.tab_bar, text="🏠 Главная", 
                                  command=lambda: self.show_tab("main"),
                                  bg=self.colors['bg_light'], fg=self.colors['fg'],
                                  activebackground=self.colors['bg_lighter'],
                                  bd=0, padx=20, pady=10, font=("Segoe UI", 10))
        self.tab_main.pack(side=tk.LEFT, padx=(10, 5))
        
        self.tab_screenshots = tk.Button(self.tab_bar, text="📸 Скриншоты", 
                                        command=lambda: self.show_tab("screenshots"),
                                        bg=self.colors['bg_light'], fg=self.colors['fg'],
                                        activebackground=self.colors['bg_lighter'],
                                        bd=0, padx=20, pady=10, font=("Segoe UI", 10))
        self.tab_screenshots.pack(side=tk.LEFT, padx=5)
        
        self.tab_settings = tk.Button(self.tab_bar, text="⚙️ Настройки", 
                                      command=lambda: self.show_tab("settings"),
                                      bg=self.colors['bg_light'], fg=self.colors['fg'],
                                      activebackground=self.colors['bg_lighter'],
                                      bd=0, padx=20, pady=10, font=("Segoe UI", 10))
        self.tab_settings.pack(side=tk.LEFT, padx=5)
        
        # Индикатор активной вкладки
        self.tab_indicator = tk.Frame(self.tab_bar, bg=self.colors['accent'], height=3)
        self.update_tab_indicator("main")
        
        # Основной контент
        self.content_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Фреймы для разных вкладок
        self.main_frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.screenshots_frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.settings_frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        
        self.create_main_tab()
        self.create_screenshots_tab()
        self.create_settings_tab()
        
        self.show_tab("main")
        
        # Нижняя панель с ником
        self.create_bottom_bar()
    
    def update_tab_indicator(self, tab_name):
        """Обновление позиции индикатора вкладки"""
        try:
            if tab_name == "main":
                x = self.tab_main.winfo_x()
                width = self.tab_main.winfo_width()
            elif tab_name == "screenshots":
                x = self.tab_screenshots.winfo_x()
                width = self.tab_screenshots.winfo_width()
            else:
                x = self.tab_settings.winfo_x()
                width = self.tab_settings.winfo_width()
            
            self.tab_indicator.place(x=x, y=37, width=width)
        except:
            pass
    
    def show_tab(self, tab_name):
        """Переключение между вкладками"""
        self.update_tab_indicator(tab_name)
        
        if tab_name == "main":
            self.main_frame.pack(fill=tk.BOTH, expand=True)
            self.screenshots_frame.pack_forget()
            self.settings_frame.pack_forget()
        elif tab_name == "screenshots":
            self.screenshots_frame.pack(fill=tk.BOTH, expand=True)
            self.main_frame.pack_forget()
            self.settings_frame.pack_forget()
        else:
            self.settings_frame.pack(fill=tk.BOTH, expand=True)
            self.main_frame.pack_forget()
            self.screenshots_frame.pack_forget()
    
    def create_bottom_bar(self):
        """Создание нижней панели"""
        bottom_bar = tk.Frame(self.root, bg=self.colors['bg_light'], height=60)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_bar.pack_propagate(False)
        
        # Левая часть - информация о RAM
        left_frame = tk.Frame(bottom_bar, bg=self.colors['bg_light'])
        left_frame.pack(side=tk.LEFT, padx=20, pady=10)
        
        tk.Label(left_frame, text="💾 RAM:", 
                bg=self.colors['bg_light'], fg=self.colors['fg'],
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 5))
        
        self.ram_info = tk.Label(left_frame, text=f"{self.max_ram} MB", 
                                bg=self.colors['bg_light'], fg=self.colors['accent'],
                                font=("Segoe UI", 12, "bold"))
        self.ram_info.pack(side=tk.LEFT)
        
        # Правая часть - ник игрока
        right_frame = tk.Frame(bottom_bar, bg=self.colors['bg_light'])
        right_frame.pack(side=tk.RIGHT, padx=20, pady=10)
        
        tk.Label(right_frame, text="👤 Ник:", 
                bg=self.colors['bg_light'], fg=self.colors['fg'],
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 8))
        
        # Комбобокс для выбора ника
        self.username_combo = ttk.Combobox(right_frame, textvariable=self.username,
                                          values=self.usernames,
                                          width=20,
                                          font=("Segoe UI", 10))
        self.username_combo.pack(side=tk.LEFT, ipady=2)
        self.username_combo.bind('<<ComboboxSelected>>', self.on_username_selected)
        
        # Кнопка для управления никами
        tk.Button(right_frame, text="⚙️", command=self.manage_usernames,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 activebackground=self.colors['accent_hover'],
                 bd=0, padx=10, pady=2, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(5, 0))
    
    def on_username_selected(self, event):
        """Обработка выбора ника из списка"""
        self.log(f"Выбран ник: {self.username.get()}", "INFO")
    
    def manage_usernames(self):
        """Окно управления никами"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Управление никами")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors['bg'])
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 500) // 2
        y = (dialog.winfo_screenheight() - 450) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Основной фрейм
        main_frame = tk.Frame(dialog, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Заголовок
        tk.Label(main_frame, text="Управление никами игроков", 
                font=("Segoe UI", 14, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(pady=(15, 10))
        
        # Список ников
        list_frame = tk.Frame(main_frame, bg=self.colors['bg_lighter'], bd=2, relief=tk.SOLID)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.colors['bg_light'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        username_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                          bg=self.colors['bg_light'], fg=self.colors['fg'],
                                          selectbackground=self.colors['accent'],
                                          bd=0, highlightthickness=0,
                                          font=("Segoe UI", 11))
        username_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=username_listbox.yview)
        
        # Заполняем список
        for name in self.usernames:
            username_listbox.insert(tk.END, name)
        
        # Поле для нового ника
        add_frame = tk.Frame(main_frame, bg=self.colors['bg_light'])
        add_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(add_frame, text="Новый ник:", 
                bg=self.colors['bg_light'], fg=self.colors['fg'],
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        new_username_var = tk.StringVar()
        new_entry = tk.Entry(add_frame, textvariable=new_username_var,
                            bg=self.colors['bg'], fg=self.colors['fg'], bd=2,
                            font=("Segoe UI", 11))
        new_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        new_entry.focus()
        
        # Кнопки управления
        btn_frame = tk.Frame(main_frame, bg=self.colors['bg_light'])
        btn_frame.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        def add_username():
            new_name = new_username_var.get().strip()
            if new_name:
                if new_name not in self.usernames:
                    self.usernames.append(new_name)
                    username_listbox.insert(tk.END, new_name)
                    self.username_combo['values'] = self.usernames
                    new_username_var.set("")
                    self.save_config()
                    self.log(f"Добавлен ник: {new_name}", "INFO")
                else:
                    messagebox.showwarning("Предупреждение", "Такой ник уже существует")
        
        def delete_selected():
            selection = username_listbox.curselection()
            if selection:
                idx = selection[0]
                name = username_listbox.get(idx)
                if len(self.usernames) > 1:
                    self.usernames.remove(name)
                    username_listbox.delete(idx)
                    self.username_combo['values'] = self.usernames
                    if self.username.get() == name:
                        self.username.set(self.usernames[0])
                    self.save_config()
                    self.log(f"Удален ник: {name}", "INFO")
                else:
                    messagebox.showwarning("Предупреждение", "Нельзя удалить последний ник")
        
        def set_selected():
            selection = username_listbox.curselection()
            if selection:
                idx = selection[0]
                name = username_listbox.get(idx)
                self.username.set(name)
                dialog.destroy()
                self.log(f"Выбран ник: {name}", "INFO")
        
        # Кнопки
        tk.Button(btn_frame, text="Добавить", command=add_username,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 activebackground=self.colors['accent_hover'],
                 bd=0, padx=15, pady=5, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=2)
        
        tk.Button(btn_frame, text="Удалить", command=delete_selected,
                 bg=self.colors['bg'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=2, padx=15, pady=3, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(btn_frame, text="Выбрать", command=set_selected,
                 bg=self.colors['bg'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=2, padx=15, pady=3, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=2)
        
        tk.Button(btn_frame, text="Закрыть", command=dialog.destroy,
                 bg=self.colors['bg'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=2, padx=15, pady=3, font=("Segoe UI", 10)).pack(side=tk.RIGHT, padx=2)
    
    def create_main_tab(self):
        """Главная вкладка со списком версий"""
        # Левая часть - список версий
        left_frame = tk.Frame(self.main_frame, bg=self.colors['bg'])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="📋 Установленные версии:", 
                font=("Segoe UI", 12, "bold"), bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor=tk.W, pady=(0, 5))
        
        list_frame = tk.Frame(left_frame, bg=self.colors['bg_lighter'], bd=2, relief=tk.SOLID)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.colors['bg_light'], troughcolor=self.colors['bg'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.versions_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                          bg=self.colors['bg_light'], fg=self.colors['fg'],
                                          selectbackground=self.colors['accent'],
                                          selectforeground=self.colors['fg'],
                                          bd=0, highlightthickness=0,
                                          font=("Consolas", 11))
        self.versions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.versions_listbox.yview)
        self.versions_listbox.bind('<<ListboxSelect>>', self.on_version_select)
        
        # Правая часть - информация и кнопки
        right_frame = tk.Frame(self.main_frame, bg=self.colors['bg'], width=350)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
        right_frame.pack_propagate(False)
        
        # Карточка информации
        info_card = tk.Frame(right_frame, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(info_card, text="ℹ️ Информация о версии", 
                font=("Segoe UI", 12, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        self.info_label = tk.Label(info_card, text="Версия не выбрана", 
                                   bg=self.colors['bg_light'], fg=self.colors['fg_secondary'],
                                   justify=tk.LEFT, font=("Segoe UI", 10))
        self.info_label.pack(anchor=tk.W, padx=15, pady=(0, 10))
        
        # Кнопки действий
        buttons_frame = tk.Frame(right_frame, bg=self.colors['bg'])
        buttons_frame.pack(fill=tk.X)
        
        tk.Button(buttons_frame, text="🚀 Запустить", command=self.launch_version,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 activebackground=self.colors['accent_hover'],
                 bd=0, padx=20, pady=8, font=("Segoe UI", 11, "bold")).pack(fill=tk.X, pady=2)
        
        tk.Button(buttons_frame, text="📦 Установить версию", command=self.install_version,
                 bg=self.colors['bg_light'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=1, padx=20, pady=6, font=("Segoe UI", 10)).pack(fill=tk.X, pady=2)
        
        tk.Button(buttons_frame, text="✏️ Переименовать", command=self.rename_version,
                 bg=self.colors['bg_light'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=1, padx=20, pady=6, font=("Segoe UI", 10)).pack(fill=tk.X, pady=2)
        
        tk.Button(buttons_frame, text="🗑️ Удалить", command=self.delete_version,
                 bg=self.colors['bg_light'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=1, padx=20, pady=6, font=("Segoe UI", 10)).pack(fill=tk.X, pady=2)
        
        tk.Button(buttons_frame, text="🔄 Обновить список", command=self.refresh_versions,
                 bg=self.colors['bg_light'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=1, padx=20, pady=6, font=("Segoe UI", 10)).pack(fill=tk.X, pady=2)
    
    def create_screenshots_tab(self):
        """Вкладка со скриншотами Minecraft"""
        # Заголовок
        tk.Label(self.screenshots_frame, text="📸 Скриншоты Minecraft", 
                font=("Segoe UI", 16, "bold"), bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor=tk.W, pady=(0, 15))
        
        # Основной контент
        content = tk.Frame(self.screenshots_frame, bg=self.colors['bg'])
        content.pack(fill=tk.BOTH, expand=True)
        
        # Левая панель - список скриншотов
        left_panel = tk.Frame(content, bg=self.colors['bg'], width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        tk.Label(left_panel, text="Список скриншотов:", 
                bg=self.colors['bg'], fg=self.colors['fg'],
                font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        
        list_frame = tk.Frame(left_panel, bg=self.colors['bg_lighter'], bd=2, relief=tk.SOLID)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.colors['bg_light'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.screenshots_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                             bg=self.colors['bg_light'], fg=self.colors['fg'],
                                             selectbackground=self.colors['accent'],
                                             bd=0, highlightthickness=0,
                                             font=("Segoe UI", 10))
        self.screenshots_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.screenshots_listbox.yview)
        self.screenshots_listbox.bind('<<ListboxSelect>>', self.on_screenshot_select)
        
        # Кнопка обновления списка
        refresh_btn = tk.Button(left_panel, text="🔄 Обновить", command=self.refresh_screenshots,
                 bg=self.colors['bg_light'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=1, padx=10, pady=5)
        refresh_btn.pack(fill=tk.X, pady=5)
        
        # Правая панель - просмотр скриншота
        right_panel = tk.Frame(content, bg=self.colors['bg'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Область для изображения
        preview_frame = tk.Frame(right_panel, bg=self.colors['bg_lighter'], bd=2, relief=tk.SUNKEN)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Label для отображения скриншота
        self.screenshot_label_display = tk.Label(preview_frame, bg=self.colors['bg_lighter'])
        self.screenshot_label_display.pack(fill=tk.BOTH, expand=True)
        
        # Информация о выбранном скриншоте
        info_frame = tk.Frame(right_panel, bg=self.colors['bg'], height=40)
        info_frame.pack(fill=tk.X)
        info_frame.pack_propagate(False)
        
        self.screenshot_name_label = tk.Label(info_frame, text="Нет выбранного скриншота",
                                            bg=self.colors['bg'], fg=self.colors['fg_secondary'])
        self.screenshot_name_label.pack(side=tk.LEFT, padx=5)
        
        # Кнопки управления
        btn_frame = tk.Frame(info_frame, bg=self.colors['bg'])
        btn_frame.pack(side=tk.RIGHT)
        
        tk.Button(btn_frame, text="📂 Открыть папку", 
                 command=self.open_screenshots_folder,
                 bg=self.colors['bg_light'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=1, padx=10, pady=2).pack(side=tk.LEFT, padx=2)
        
        tk.Button(btn_frame, text="🗑️ Удалить", 
                 command=self.delete_screenshot,
                 bg=self.colors['bg_light'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=1, padx=10, pady=2).pack(side=tk.LEFT, padx=2)
    
    def create_settings_tab(self):
        """Вкладка настроек"""
        # Карточка с настройками
        settings_card = tk.Frame(self.settings_frame, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        settings_card.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        tk.Label(settings_card, text="⚙️ Настройки лаунчера", 
                font=("Segoe UI", 14, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W, padx=20, pady=(15, 5))
        
        # Папка Minecraft
        path_frame = tk.Frame(settings_card, bg=self.colors['bg_light'])
        path_frame.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(path_frame, text="📁 Папка Minecraft:", 
                font=("Segoe UI", 11, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W)
        
        path_control = tk.Frame(path_frame, bg=self.colors['bg_light'])
        path_control.pack(fill=tk.X, pady=(5, 0))
        
        self.path_var = tk.StringVar(value=self.minecraft_directory)
        path_entry = tk.Entry(path_control, textvariable=self.path_var,
                              bg=self.colors['bg'], fg=self.colors['fg'],
                              insertbackground=self.colors['fg'], bd=2,
                              font=("Segoe UI", 10))
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))
        
        def browse_path():
            path = filedialog.askdirectory(title="Выберите папку Minecraft")
            if path:
                self.path_var.set(path)
        
        tk.Button(path_control, text="Обзор", command=browse_path,
                 bg=self.colors['bg'], fg=self.colors['fg'],
                 bd=2, padx=10, pady=2).pack(side=tk.RIGHT)
        
        # Настройки RAM
        ram_frame = tk.Frame(settings_card, bg=self.colors['bg_light'])
        ram_frame.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(ram_frame, text="💾 Выделенная память (RAM):", 
                font=("Segoe UI", 11, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W)
        
        # Поле для точного ввода RAM
        ram_input_frame = tk.Frame(ram_frame, bg=self.colors['bg_light'])
        ram_input_frame.pack(fill=tk.X, pady=(5, 10))
        
        tk.Label(ram_input_frame, text="MB:", 
                bg=self.colors['bg_light'], fg=self.colors['fg'],
                font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 5))
        
        self.ram_entry_var = tk.StringVar(value=str(self.max_ram))
        ram_entry = tk.Entry(ram_input_frame, textvariable=self.ram_entry_var,
                            bg=self.colors['bg'], fg=self.colors['fg'],
                            insertbackground=self.colors['fg'], bd=2,
                            font=("Segoe UI", 11), width=10)
        ram_entry.pack(side=tk.LEFT, ipady=3)
        ram_entry.bind('<Return>', self.apply_ram_from_entry)
        
        tk.Label(ram_input_frame, text="(512 - 16384)", 
                bg=self.colors['bg_light'], fg=self.colors['fg_secondary'],
                font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Кнопка применения
        tk.Button(ram_input_frame, text="Применить", command=self.apply_ram_from_entry,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 activebackground=self.colors['accent_hover'],
                 bd=0, padx=10, pady=2, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Слайдер RAM
        ram_control = tk.Frame(ram_frame, bg=self.colors['bg_light'])
        ram_control.pack(fill=tk.X, pady=(5, 0))
        
        self.ram_var = tk.IntVar(value=self.max_ram)
        
        # Метка для отображения значения
        self.ram_label = tk.Label(ram_control, text=f"{self.max_ram} MB", 
                                  bg=self.colors['bg_light'], fg=self.colors['accent'],
                                  font=("Segoe UI", 11, "bold"))
        self.ram_label.pack(side=tk.RIGHT)
        
        # Слайдер
        ram_slider = ttk.Scale(ram_control, from_=512, to_=16384, orient=tk.HORIZONTAL,
                              variable=self.ram_var, command=self.update_ram_from_slider)
        ram_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Java аргументы
        java_frame = tk.Frame(settings_card, bg=self.colors['bg_light'])
        java_frame.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(java_frame, text="☕ Дополнительные аргументы Java:", 
                font=("Segoe UI", 11, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(anchor=tk.W)
        
        self.args_var = tk.StringVar(value=self.java_args)
        args_entry = tk.Entry(java_frame, textvariable=self.args_var,
                              bg=self.colors['bg'], fg=self.colors['fg'],
                              insertbackground=self.colors['fg'], bd=2,
                              font=("Segoe UI", 10))
        args_entry.pack(fill=tk.X, pady=(5, 5), ipady=5)
        
        tk.Label(java_frame, text="Пример: -XX:+UseG1GC -Dsun.rmi.dgc.server.gcInterval=2147483646",
                bg=self.colors['bg_light'], fg=self.colors['fg_secondary'],
                font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        # Кнопка сохранения
        save_btn = tk.Button(settings_card, text="💾 Сохранить настройки", command=self.save_settings,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 activebackground=self.colors['accent_hover'],
                 bd=0, padx=30, pady=10, font=("Segoe UI", 11, "bold"))
        save_btn.pack(pady=20)
    
    def update_ram_from_slider(self, value):
        """Обновление RAM из слайдера"""
        try:
            ram_value = int(float(value))
            self.ram_label.config(text=f"{ram_value} MB")
            self.ram_entry_var.set(str(ram_value))
            self.max_ram = ram_value
            self.ram_info.config(text=f"{ram_value} MB")
        except:
            pass
    
    def apply_ram_from_entry(self, event=None):
        """Применение значения RAM из поля ввода"""
        try:
            new_ram = int(self.ram_entry_var.get())
            if 512 <= new_ram <= 16384:
                self.max_ram = new_ram
                self.ram_var.set(new_ram)
                self.ram_label.config(text=f"{new_ram} MB")
                self.ram_info.config(text=f"{new_ram} MB")
                self.log(f"RAM изменена на {new_ram} MB", "INFO")
            else:
                messagebox.showwarning("Предупреждение", "Значение должно быть от 512 до 16384 MB")
                self.ram_entry_var.set(str(self.max_ram))
        except ValueError:
            messagebox.showwarning("Предупреждение", "Введите корректное число")
            self.ram_entry_var.set(str(self.max_ram))
    
    def save_settings(self):
        """Сохранение настроек"""
        new_path = self.path_var.get().strip()
        if new_path and new_path != self.minecraft_directory:
            if messagebox.askyesno("Подтверждение", "Изменить папку Minecraft?"):
                self.minecraft_directory = new_path
                self.create_directories()
                self.refresh_versions()
                self.refresh_screenshots()
        
        self.apply_ram_from_entry()
        self.java_args = self.args_var.get().strip()
        self.save_config()
        
        messagebox.showinfo("Успех", "Настройки сохранены")
        self.show_tab("main")
    
    def refresh_versions(self):
        """Обновление списка версий"""
        try:
            versions_dir = os.path.join(self.minecraft_directory, "versions")
            self.installed_versions = []
            
            if os.path.exists(versions_dir):
                for item in os.listdir(versions_dir):
                    item_path = os.path.join(versions_dir, item)
                    if os.path.isdir(item_path):
                        json_path = os.path.join(item_path, f"{item}.json")
                        jar_path = os.path.join(item_path, f"{item}.jar")
                        if os.path.exists(json_path) and os.path.exists(jar_path):
                            self.installed_versions.append(item)
            
            self.installed_versions.sort()
            self.versions_listbox.delete(0, tk.END)
            
            for v in self.installed_versions:
                display = self.version_names.get(v, v)
                self.versions_listbox.insert(tk.END, f"  {display}")
            
            self.log(f"Найдено версий: {len(self.installed_versions)}", "INFO")
        except Exception as e:
            self.log(f"Ошибка обновления списка версий: {e}", "ERROR")
    
    def on_version_select(self, event):
        """Выбор версии из списка"""
        try:
            selection = self.versions_listbox.curselection()
            if selection:
                idx = selection[0]
                if idx < len(self.installed_versions):
                    self.selected_version = self.installed_versions[idx]
                    
                    display = self.version_names.get(self.selected_version, self.selected_version)
                    
                    version_dir = os.path.join(self.minecraft_directory, "versions", self.selected_version)
                    size_mb = 0
                    try:
                        size = sum(f.stat().st_size for f in Path(version_dir).rglob('*') if f.is_file())
                        size_mb = size / (1024 * 1024)
                    except:
                        pass
                    
                    info_text = f"📝 Название: {display}\n📁 Версия: {self.selected_version}\n💾 Размер: {size_mb:.1f} MB"
                    self.info_label.config(text=info_text)
                    self.log(f"Выбрана версия: {self.selected_version}", "INFO")
        except Exception as e:
            self.log(f"Ошибка выбора версии: {e}", "ERROR")
    
    def get_java_args(self):
        """Формирование аргументов Java"""
        args = [f"-Xmx{self.max_ram}M", f"-Xms{self.min_ram}M"]
        if self.java_args:
            args.extend(self.java_args.split())
        return args
    
    def launch_version(self):
        """Запуск выбранной версии"""
        if not self.selected_version:
            messagebox.showwarning("Предупреждение", "Выберите версию")
            return
        
        if self.minecraft_running:
            messagebox.showwarning("Предупреждение", "Minecraft уже запущен")
            return
        
        username = self.username.get().strip() or "Steve"
        
        try:
            # Генерируем новый UUID для каждой сессии
            session_uuid = self.generate_uuid()
            
            options = {
                "username": username,
                "uuid": session_uuid,
                "token": "",
                "gameDirectory": self.minecraft_directory,
                "jvmArguments": self.get_java_args()
            }
            
            cmd = minecraft_launcher_lib.command.get_minecraft_command(
                self.selected_version, self.minecraft_directory, options
            )
            
            logs_dir = os.path.join(self.minecraft_directory, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            
            log_arg = f"-Dminecraft.logs={logs_dir}"
            
            # Вставляем аргумент логов в команду
            java_idx = next(i for i, p in enumerate(cmd) if 'java' in p)
            mem_end = java_idx + 1
            while mem_end < len(cmd) and cmd[mem_end].startswith('-X'):
                mem_end += 1
            cmd = cmd[:mem_end] + [log_arg] + cmd[mem_end:]
            
            display = self.version_names.get(self.selected_version, self.selected_version)
            self.log(f"Запуск {display} для {username} (UUID: {session_uuid})", "INFO")
            
            # Создаем процесс
            self.minecraft_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                cwd=self.minecraft_directory,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            self.minecraft_running = True
            
            # Функция для чтения вывода
            def read_output(pipe, is_err):
                prefix = "[Minecraft-ERR]" if is_err else "[Minecraft]"
                try:
                    for line in iter(pipe.readline, ''):
                        if line and line.strip():
                            self.log(f"{prefix} {line.strip()}", "INFO")
                except:
                    pass
            
            # Запускаем потоки для чтения вывода
            threading.Thread(target=read_output, args=(self.minecraft_process.stdout, False), daemon=True).start()
            threading.Thread(target=read_output, args=(self.minecraft_process.stderr, True), daemon=True).start()
            
            # Функция ожидания завершения
            def wait_process():
                try:
                    self.minecraft_process.wait()
                except:
                    pass
                finally:
                    self.minecraft_running = False
                    self.log("Minecraft остановлен", "INFO")
            
            threading.Thread(target=wait_process, daemon=True).start()
            
            messagebox.showinfo("Запуск", f"{display} запущен")
            
        except Exception as e:
            self.log(f"Ошибка запуска: {e}", "ERROR")
            messagebox.showerror("Ошибка", str(e))
    
    def install_version(self):
        """Установка новой версии с визуальным прогрессом"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Установка новой версии")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors['bg'])
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 500) // 2
        y = (dialog.winfo_screenheight() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        
        frame = tk.Frame(dialog, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        content = tk.Frame(frame, bg=self.colors['bg_light'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(content, text="Установка новой версии", 
                font=("Segoe UI", 14, "bold"), bg=self.colors['bg_light'], fg=self.colors['fg']).pack(pady=(0, 15))
        
        tk.Label(content, text="Введите версию Minecraft:", 
                bg=self.colors['bg_light'], fg=self.colors['fg'],
                font=("Segoe UI", 11)).pack(anchor=tk.W)
        
        ver_var = tk.StringVar()
        entry = tk.Entry(content, textvariable=ver_var,
                        bg=self.colors['bg'], fg=self.colors['fg'], bd=2,
                        font=("Segoe UI", 11))
        entry.pack(fill=tk.X, pady=5, ipady=8)
        entry.focus()
        
        tk.Label(content, text="Название (необязательно):", 
                bg=self.colors['bg_light'], fg=self.colors['fg'],
                font=("Segoe UI", 11)).pack(anchor=tk.W, pady=(10, 0))
        
        name_var = tk.StringVar()
        name_entry = tk.Entry(content, textvariable=name_var,
                             bg=self.colors['bg'], fg=self.colors['fg'], bd=2,
                             font=("Segoe UI", 11))
        name_entry.pack(fill=tk.X, pady=5, ipady=8)
        
        # Прогресс бар
        progress_bar = ttk.Progressbar(content, mode='indeterminate', length=400)
        status_label = tk.Label(content, text="", bg=self.colors['bg_light'], fg=self.colors['fg_secondary'])
        
        btn_frame = tk.Frame(content, bg=self.colors['bg_light'])
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Кнопка отмены
        tk.Button(btn_frame, text="Отмена", command=dialog.destroy,
                 bg=self.colors['bg'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=(0, 10))
        
        def start_install():
            ver = ver_var.get().strip()
            if not ver:
                messagebox.showwarning("Предупреждение", "Введите версию")
                return
            
            name = name_var.get().strip()
            
            # Показываем прогресс
            progress_bar.pack(pady=10)
            status_label.pack()
            progress_bar.start()
            status_label.config(text="Начало установки...")
            
            # Отключаем кнопки
            for widget in btn_frame.winfo_children():
                widget.config(state=tk.DISABLED)
            entry.config(state=tk.DISABLED)
            name_entry.config(state=tk.DISABLED)
            
            def do_install():
                try:
                    status_label.config(text="Загрузка файлов...")
                    self.log(f"Установка {ver}...", "INFO")
                    
                    minecraft_launcher_lib.install.install_minecraft_version(ver, self.minecraft_directory)
                    
                    if name:
                        self.version_names[ver] = name
                        self.save_config()
                    
                    status_label.config(text="Установка завершена!")
                    progress_bar.stop()
                    
                    self.root.after(500, dialog.destroy)
                    self.root.after(0, self.refresh_versions)
                    self.root.after(0, lambda v=ver: messagebox.showinfo("Успех", f"Версия {v} установлена"))
                    self.log(f"Версия {ver} установлена", "INFO")
                    
                except Exception as e:
                    progress_bar.stop()
                    status_label.config(text="Ошибка установки")
                    self.log(f"Ошибка установки {ver}: {e}", "ERROR")
                    
                    # Включаем кнопки обратно
                    self.root.after(0, lambda: self.enable_install_buttons(btn_frame, entry, name_entry))
                    self.root.after(0, lambda err=str(e): messagebox.showerror("Ошибка", err))
            
            threading.Thread(target=do_install, daemon=True).start()
        
        # Кнопка установки
        tk.Button(btn_frame, text="Установить", command=start_install,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 activebackground=self.colors['accent_hover'],
                 bd=0, padx=25, pady=6, font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT)
    
    def enable_install_buttons(self, btn_frame, entry, name_entry):
        """Включение кнопок после ошибки"""
        try:
            for widget in btn_frame.winfo_children():
                widget.config(state=tk.NORMAL)
            entry.config(state=tk.NORMAL)
            name_entry.config(state=tk.NORMAL)
        except:
            pass
    
    def rename_version(self):
        """Переименование версии"""
        if not self.selected_version:
            messagebox.showwarning("Предупреждение", "Выберите версию")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Переименование версии")
        dialog.geometry("450x230")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors['bg'])
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 450) // 2
        y = (dialog.winfo_screenheight() - 230) // 2
        dialog.geometry(f"+{x}+{y}")
        
        frame = tk.Frame(dialog, bg=self.colors['bg_light'], bd=2, relief=tk.SOLID)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        content = tk.Frame(frame, bg=self.colors['bg_light'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(content, text=f"Оригинальная версия: {self.selected_version}", 
                bg=self.colors['bg_light'], fg=self.colors['fg_secondary'],
                font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(0, 10))
        
        tk.Label(content, text="Новое название:", 
                bg=self.colors['bg_light'], fg=self.colors['fg'],
                font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(5, 5))
        
        current = self.version_names.get(self.selected_version, "")
        name_var = tk.StringVar(value=current)
        entry = tk.Entry(content, textvariable=name_var,
                        bg=self.colors['bg'], fg=self.colors['fg'], bd=2,
                        font=("Segoe UI", 11))
        entry.pack(fill=tk.X, ipady=8, pady=(0, 15))
        entry.select_range(0, tk.END)
        entry.focus()
        
        btn_frame = tk.Frame(content, bg=self.colors['bg_light'])
        btn_frame.pack(fill=tk.X)
        
        # Кнопка отмены
        tk.Button(btn_frame, text="Отмена", command=dialog.destroy,
                 bg=self.colors['bg'], fg=self.colors['fg'],
                 activebackground=self.colors['bg_lighter'],
                 bd=2, padx=20, pady=5).pack(side=tk.LEFT, padx=(0, 10))
        
        def save():
            new = name_var.get().strip()
            if new:
                self.version_names[self.selected_version] = new
            else:
                if self.selected_version in self.version_names:
                    del self.version_names[self.selected_version]
            self.save_config()
            dialog.destroy()
            self.refresh_versions()
        
        # Кнопка сохранения
        tk.Button(btn_frame, text="Сохранить", command=save,
                 bg=self.colors['accent'], fg=self.colors['fg'],
                 activebackground=self.colors['accent_hover'],
                 bd=0, padx=25, pady=6, font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT)
    
    def delete_version(self):
        """Удаление версии"""
        if not self.selected_version:
            messagebox.showwarning("Предупреждение", "Выберите версию")
            return
        
        display = self.version_names.get(self.selected_version, self.selected_version)
        if not messagebox.askyesno("Подтверждение", f"Удалить версию '{display}'?"):
            return
        
        try:
            ver_dir = os.path.join(self.minecraft_directory, "versions", self.selected_version)
            if os.path.exists(ver_dir):
                shutil.rmtree(ver_dir)
                self.log(f"Удалена версия: {self.selected_version}", "INFO")
            
            if self.selected_version in self.version_names:
                del self.version_names[self.selected_version]
            self.save_config()
            
            self.selected_version = None
            self.refresh_versions()
            self.info_label.config(text="Версия не выбрана")
            
            messagebox.showinfo("Успех", "Версия удалена")
            
        except Exception as e:
            self.log(f"Ошибка удаления: {e}", "ERROR")
            messagebox.showerror("Ошибка", str(e))
    
    # Методы для работы со скриншотами
    def refresh_screenshots(self):
        """Обновление списка скриншотов"""
        try:
            screenshots_dir = os.path.join(self.minecraft_directory, "screenshots")
            self.screenshots = []
            self.screenshots_listbox.delete(0, tk.END)
            
            if os.path.exists(screenshots_dir):
                for file in os.listdir(screenshots_dir):
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        self.screenshots.append(file)
                
                self.screenshots.sort(reverse=True)
                
                for ss in self.screenshots:
                    display_name = ss if len(ss) < 30 else ss[:27] + "..."
                    self.screenshots_listbox.insert(tk.END, f"  {display_name}")
            
            if not self.screenshots:
                self.screenshots_listbox.insert(tk.END, "  Нет скриншотов")
                if self.screenshot_name_label:
                    self.screenshot_name_label.config(text="Нет скриншотов")
                if self.screenshot_label_display:
                    self.screenshot_label_display.config(image='', text="Нет скриншотов")
        except Exception as e:
            self.log(f"Ошибка обновления списка скриншотов: {e}", "ERROR")
    
    def on_screenshot_select(self, event):
        """Выбор скриншота из списка"""
        try:
            selection = self.screenshots_listbox.curselection()
            if selection and self.screenshots:
                idx = selection[0]
                if idx < len(self.screenshots):
                    self.current_screenshot = idx
                    filename = self.screenshots[idx]
                    if self.screenshot_name_label:
                        self.screenshot_name_label.config(text=f"Выбран: {filename}")
                    self.display_screenshot(filename)
        except Exception as e:
            self.log(f"Ошибка выбора скриншота: {e}", "ERROR")
    
    def display_screenshot(self, filename):
        """Отображение выбранного скриншота"""
        try:
            filepath = os.path.join(self.minecraft_directory, "screenshots", filename)
            
            if not os.path.exists(filepath):
                if self.screenshot_label_display:
                    self.screenshot_label_display.config(image='', text="Файл не найден")
                return
            
            # Открываем изображение
            pil_image = Image.open(filepath)
            
            # Получаем размеры области просмотра
            if self.screenshot_label_display:
                preview_width = self.screenshot_label_display.winfo_width()
                preview_height = self.screenshot_label_display.winfo_height()
                
                if preview_width <= 1 or preview_height <= 1:
                    preview_width = 600
                    preview_height = 400
                
                # Масштабируем изображение
                img_width, img_height = pil_image.size
                scale = min(preview_width / img_width, preview_height / img_height, 1.0)
                
                if scale < 1.0:
                    new_width = int(img_width * scale)
                    new_height = int(img_height * scale)
                    pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Конвертируем для Tkinter
                photo = ImageTk.PhotoImage(pil_image)
                
                # Сохраняем ссылку
                self.photo_images.append(photo)
                
                # Отображаем
                self.screenshot_label_display.config(image=photo, text='')
            
        except Exception as e:
            self.log(f"Ошибка загрузки скриншота: {e}", "ERROR")
            if self.screenshot_label_display:
                self.screenshot_label_display.config(image='', text=f"Ошибка: {str(e)}")
    
    def open_screenshots_folder(self):
        """Открытие папки со скриншотами"""
        try:
            screenshots_dir = os.path.join(self.minecraft_directory, "screenshots")
            if os.path.exists(screenshots_dir):
                os.startfile(screenshots_dir)
            else:
                messagebox.showinfo("Информация", "Папка со скриншотами еще не создана")
        except Exception as e:
            self.log(f"Ошибка открытия папки: {e}", "ERROR")
    
    def delete_screenshot(self):
        """Удаление выбранного скриншота"""
        try:
            if not self.screenshots or self.current_screenshot >= len(self.screenshots):
                messagebox.showwarning("Предупреждение", "Выберите скриншот")
                return
            
            filename = self.screenshots[self.current_screenshot]
            if messagebox.askyesno("Подтверждение", f"Удалить скриншот '{filename}'?"):
                filepath = os.path.join(self.minecraft_directory, "screenshots", filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    self.log(f"Удален скриншот: {filename}", "INFO")
                    self.refresh_screenshots()
                    if self.screenshot_name_label:
                        self.screenshot_name_label.config(text="Скриншот удален")
                    if self.screenshot_label_display:
                        self.screenshot_label_display.config(image='', text="Скриншот удален")
                    self.photo_images.clear()
        except Exception as e:
            self.log(f"Ошибка удаления скриншота: {e}", "ERROR")
            messagebox.showerror("Ошибка", str(e))

def main():
    root = tk.Tk()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = MinecraftLauncherGUI(root)
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Ошибка: {e}")
        input("Нажмите Enter для выхода...")