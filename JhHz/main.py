import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import subprocess
import sys
import os
import threading
import json
from pathlib import Path
from queue import Queue
import ctypes
import traceback
import importlib.util

mutex = None  # 全局变量，保证互斥锁存活

def log_crash(exc_type, exc_value, exc_traceback):
    with open("crash.log", "a", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

sys.excepthook = log_crash

def is_already_running():
    global mutex
    mutex_name = "Global\\JhHzPythonManager"  # 全局作用域
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        return True
    return False

def get_pip_path():
    # 获取当前python的Scripts目录
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    pip_path = os.path.join(scripts_dir, "pip.exe")
    if os.path.exists(pip_path):
        return pip_path
    # 兼容部分环境
    pip_path = os.path.join(scripts_dir, "pip3.exe")
    if os.path.exists(pip_path):
        return pip_path
    return None

def get_package_real_path(package_name):
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            return None
        if spec.submodule_search_locations:
            # 包是一个目录
            return spec.submodule_search_locations[0]
        elif spec.origin:
            # 包是单文件
            return spec.origin
    except Exception:
        pass
    return None

def get_package_size(path):
    def sizeof_fmt(num, suffix="B"):
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Y{suffix}"
    try:
        if os.path.isdir(path):
            total = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.isfile(fp):
                        total += os.path.getsize(fp)
            return sizeof_fmt(total)
        elif os.path.isfile(path):
            return sizeof_fmt(os.path.getsize(path))
        else:
            return "未知"
    except Exception:
        return "未知"

class JhHzApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JhHz - Python环境管理器")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        # 设置样式
        style = tb.Style()
        
        self.setup_ui()
        self.check_python_environment()
        
        # 创建线程安全的日志队列
        self.log_queue = Queue()
        self.log_thread = threading.Thread(target=self.process_log_queue, daemon=True)
        self.log_thread.start()

        # 创建用于获取包详细信息的队列和工作线程
        self.details_queue = Queue()
        self.details_worker_thread = threading.Thread(target=self.details_worker, daemon=True)
        self.details_worker_thread.start()
        
    def setup_ui(self):
        # 主框架
        main_frame = tb.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 标题
        title_label = tb.Label(main_frame, text="JhHz Python环境管理器", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Python环境状态
        tb.Label(main_frame, text="Python环境状态:", font=("Arial", 12, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 10))
        
        self.status_frame = tb.Frame(main_frame)
        self.status_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        self.status_label = tb.Label(self.status_frame, text="检测中...", 
                                     font=("Arial", 10))
        self.status_label.pack(side=tk.LEFT)
        
        self.version_label = tb.Label(self.status_frame, text="", 
                                      font=("Arial", 10))
        self.version_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # 操作按钮
        button_frame = tb.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(0, 20))
        
        self.install_python_btn = tb.Button(button_frame, text="安装Python环境", 
                                            command=self.install_python)
        self.install_python_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.refresh_btn = tb.Button(button_frame, text="刷新检测", 
                                     command=self.check_python_environment)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 已安装包检测按钮
        self.check_packages_btn = tb.Button(button_frame, text="检测已安装包", 
                                            command=self.check_installed_packages)
        self.check_packages_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 已安装包显示区域
        packages_status_frame = tb.LabelFrame(main_frame, text="已安装的包", padding="10")
        packages_status_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        packages_status_frame.columnconfigure(0, weight=1)
        packages_status_frame.rowconfigure(0, weight=1)
        
        # 创建Treeview来显示已安装的包
        self.packages_tree = tb.Treeview(packages_status_frame, columns=("version", "size", "location"), 
                                         show="tree headings", height=8)
        self.packages_tree.heading("#0", text="包名")
        self.packages_tree.heading("version", text="版本")
        self.packages_tree.heading("size", text="大小")
        self.packages_tree.heading("location", text="安装位置")
        
        # 设置列宽
        self.packages_tree.column("#0", width=200)
        self.packages_tree.column("version", width=100)
        self.packages_tree.column("size", width=100)
        self.packages_tree.column("location", width=300)
        
        # 添加右键菜单
        self.packages_context_menu = tk.Menu(self.root, tearoff=0)
        self.packages_context_menu.add_command(label="查看详细信息", command=self.show_package_details)
        self.packages_context_menu.add_command(label="打开安装目录", command=self.open_package_directory)
        self.packages_context_menu.add_separator()
        self.packages_context_menu.add_command(label="卸载包", command=self.uninstall_package)
        
        # 绑定右键事件
        self.packages_tree.bind("<Button-3>", self.show_context_menu)
        
        # 添加滚动条
        packages_scrollbar = tb.Scrollbar(packages_status_frame, orient=tk.VERTICAL, 
                                          command=self.packages_tree.yview)
        self.packages_tree.configure(yscrollcommand=packages_scrollbar.set)
        
        self.packages_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        packages_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 包管理区域
        tb.Label(main_frame, text="Python包管理:", font=("Arial", 12, "bold")).grid(
            row=5, column=0, sticky=tk.W, pady=(20, 10))
        
        # 常用包列表
        packages_frame = tb.LabelFrame(main_frame, text="常用包", padding="10")
        packages_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        packages_frame.columnconfigure(0, weight=1)
        
        self.common_packages = [
            "requests", "beautifulsoup4", "selenium", "numpy", "pandas", 
            "matplotlib", "flask", "django", "pillow", "openpyxl"
        ]
        
        self.package_vars = {}
        columns = 3  # 每行显示3个
        ttk.Label(packages_frame, text="常用包", font=("微软雅黑", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        for i, package in enumerate(self.common_packages):
            var = tk.BooleanVar()
            self.package_vars[package] = var
            cb = tb.Checkbutton(packages_frame, text=package, variable=var, bootstyle="round-toggle")
            cb.grid(row=1 + i // columns, column=i % columns, sticky="w", padx=20, pady=5)
        
        # 自定义包安装
        custom_frame = tb.Frame(main_frame)
        custom_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        custom_frame.columnconfigure(1, weight=1)
        
        tb.Label(custom_frame, text="自定义包:").grid(row=0, column=0, sticky=tk.W)
        self.custom_package_entry = tb.Entry(custom_frame)
        self.custom_package_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 10))
        tb.Button(custom_frame, text="安装", 
                  command=self.install_custom_package).grid(row=0, column=2)
        
        # 安装按钮
        tb.Button(main_frame, text="安装选中的包", 
                  command=self.install_selected_packages).grid(row=8, column=0, columnspan=3, pady=10)
        
        # 日志区域
        log_frame = tb.LabelFrame(main_frame, text="操作日志", padding="10")
        log_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(20, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(9, weight=1)
        
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        scrollbar = tb.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
    def log_message(self, message):
        """添加日志消息"""
        self.log_queue.put(message)
        
    def process_log_queue(self):
        """处理日志队列"""
        while True:
            message = self.log_queue.get()
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
            self.root.update_idletasks()
            self.log_queue.task_done()
        
    def check_python_environment(self):
        """检测Python环境"""
        def check():
            try:
                # 检查Python版本
                result = subprocess.run([sys.executable, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version = result.stdout.strip()
                    self.status_label.config(text="✓ Python已安装", foreground="green")
                    self.version_label.config(text=f"版本: {version}")
                    self.install_python_btn.config(state="disabled")
                    self.check_packages_btn.config(state="normal")
                    self.log_message(f"检测到Python环境: {version}")
                else:
                    self.status_label.config(text="✗ Python未安装", foreground="red")
                    self.version_label.config(text="")
                    self.install_python_btn.config(state="normal")
                    self.check_packages_btn.config(state="disabled")
                    self.log_message("未检测到Python环境")
            except Exception as e:
                self.status_label.config(text="✗ 检测失败", foreground="red")
                self.version_label.config(text="")
                self.install_python_btn.config(state="normal")
                self.check_packages_btn.config(state="disabled")
                self.log_message(f"检测失败: {str(e)}")
        
        # 在新线程中执行检测
        threading.Thread(target=check, daemon=True).start()
        
    def check_installed_packages(self):
        """检测已安装的包，优化UI响应"""
        def check():
            self.log_message("开始检测已安装的包...")
            
            # 使用 after 在主线程中清空UI
            def clear_tree():
                self.packages_tree.delete(*self.packages_tree.get_children())
            self.root.after(0, clear_tree)

            try:
                pip_path = get_pip_path()
                if pip_path:
                    result = subprocess.run([pip_path, "list", "--format=json"],
                                          capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
                else:
                    # fallback
                    result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"],
                                          capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
                
                if result.returncode != 0:
                    self.log_message(f"检测失败: {result.stderr}")
                    self.root.after(0, messagebox.showerror, "错误", "无法获取已安装的包列表")
                    return

                packages = json.loads(result.stdout)
                packages.sort(key=lambda x: x['name'].lower())
                
                self.log_message(f"检测到 {len(packages)} 个包，正在快速加载列表...")

                # 先快速填充列表，详细信息后续更新
                def populate_initial_list():
                    for package in packages:
                        self.packages_tree.insert("", "end", text=package['name'], 
                                                 values=(package['version'], "获取中...", "获取中..."))
                    self.log_message("包列表初步加载完成，正在后台获取详细信息...")
                    # 将获取详细信息的任务放入队列
                    self.get_packages_details()
                
                self.root.after(0, populate_initial_list)

                self.log_message(f"pip list stdout: {result.stdout}")
                self.log_message(f"pip list stderr: {result.stderr}")

            except json.JSONDecodeError as e:
                self.log_message(f"解析包列表失败: {str(e)}")
                self.root.after(0, messagebox.showerror, "错误", "解析包列表失败")
            except Exception as e:
                self.log_message(f"检测异常: {str(e)}")
                self.root.after(0, messagebox.showerror, "错误", f"检测异常: {str(e)}")
                
        threading.Thread(target=check, daemon=True).start()

    def get_packages_details(self):
        """将获取包详细信息的任务添加到队列中"""
        for item_id in self.packages_tree.get_children():
            if self.packages_tree.exists(item_id):
                package_name = self.packages_tree.item(item_id, "text")
                self.details_queue.put((item_id, package_name))

    def details_worker(self):
        """处理获取包详细信息队列的后台工作线程"""
        while True:
            try:
                item_id, package_name = self.details_queue.get()

                location = self.get_package_location(package_name)
                real_path = get_package_real_path(package_name)
                size = get_package_size(real_path) if real_path else "未知"

                # 直接调度一个简单的方法来更新UI，这是更健壮的方式
                self.root.after(0, self._update_tree_item, item_id, location, size)
                
                self.details_queue.task_done()
            except Exception as e:
                self.log_message(f"包详细信息处理异常: {e}")

    def _update_tree_item(self, item_id, location, size):
        """在主线程中安全地更新Treeview中的单个项目"""
        if self.packages_tree.exists(item_id):
            current_values = self.packages_tree.item(item_id, "values")
            current_version = current_values[0] if current_values else ""
            self.packages_tree.item(item_id, values=(current_version, size, location))

    def get_package_location(self, package_name):
        """通过 pip show 获取包的安装位置(Windows优化)"""
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", package_name],
                capture_output=True, text=True, timeout=15, encoding='utf-8', errors='ignore',
                startupinfo=startupinfo
            )
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith('Location:'):
                        location = line.split(':', 1)[1].strip()
                        return str(Path(location).resolve())
            return "未知"
        except Exception:
            return "未知"
        
    def install_python(self):
        """安装Python环境"""
        def install():
            self.log_message("开始安装Python环境...")
            try:
                # 这里可以集成Python安装程序
                # 暂时显示提示信息
                messagebox.showinfo("安装Python", 
                                  "请访问 https://www.python.org/downloads/ 下载并安装Python")
                self.log_message("请手动安装Python环境")
            except Exception as e:
                self.log_message(f"安装失败: {str(e)}")
                messagebox.showerror("错误", f"安装失败: {str(e)}")
        
        threading.Thread(target=install, daemon=True).start()
        
    def install_custom_package(self):
        """安装自定义输入的包"""
        package_name = self.custom_package_entry.get().strip()
        if not package_name:
            messagebox.showwarning("警告", "请输入要安装的包名")
            return

        # 使用通用安装逻辑
        self.run_install_task([package_name])

    def run_install_task(self, packages_to_install):
        """通用安装任务执行器，在后台线程中安装包列表"""
        def install():
            for package_name in packages_to_install:
                self.log_message(f"开始安装 {package_name}...")
                try:
                    # 使用 --no-cache-dir 避免缓存问题，并设置较长超时
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", package_name, "--no-cache-dir"],
                        capture_output=True, text=True, timeout=300, encoding='utf-8', errors='ignore'
                    )
                    
                    # 在主线程中显示结果
                    if result.returncode == 0:
                        self.log_message(f"✓ {package_name} 安装成功")
                        self.root.after(0, messagebox.showinfo, "成功", f"{package_name} 安装成功")
                    else:
                        error_message = result.stderr or result.stdout
                        self.log_message(f"✗ {package_name} 安装失败: {error_message}")
                        self.root.after(0, messagebox.showerror, "错误", f"{package_name} 安装失败: {error_message}")
                        
                except Exception as e:
                    self.log_message(f"✗ {package_name} 安装异常: {str(e)}")
                    self.root.after(0, messagebox.showerror, "错误", f"安装异常: {str(e)}")
            
            # 所有安装任务完成后，在主线程刷新包列表
            self.root.after(0, self.check_installed_packages)

        threading.Thread(target=install, daemon=True).start()

    def install_selected_packages(self):
        """安装选中的包"""
        selected_packages = [pkg for pkg, var in self.package_vars.items() if var.get()]
        if not selected_packages:
            messagebox.showwarning("警告", "请选择要安装的包")
            return
            
        def install():
            self.log_message(f"开始安装包: {', '.join(selected_packages)}")
            for package in selected_packages:
                try:
                    self.log_message(f"正在安装 {package}...")
                    result = subprocess.run([sys.executable, "-m", "pip", "install", package],
                                          capture_output=True, text=True, timeout=300)
                    if result.returncode == 0:
                        self.log_message(f"✓ {package} 安装成功")
                    else:
                        self.log_message(f"✗ {package} 安装失败: {result.stderr}")
                except Exception as e:
                    self.log_message(f"✗ {package} 安装异常: {str(e)}")

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击的项目
        item = self.packages_tree.identify_row(event.y)
        if item:
            # 选中该项目
            self.packages_tree.selection_set(item)
            # 显示菜单
            self.packages_context_menu.post(event.x_root, event.y_root)
    
    def show_package_details(self):
        """显示包的详细信息"""
        selection = self.packages_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个包")
            return
        
        package_name = self.packages_tree.item(selection[0], "text")
        
        def get_details():
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "show", package_name],
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    details = result.stdout
                    
                    # 创建详细信息窗口
                    details_window = tk.Toplevel(self.root)
                    details_window.title(f"包详细信息 - {package_name}")
                    details_window.geometry("600x400")
                    details_window.resizable(True, True)
                    
                    # 创建文本框显示详细信息
                    text_frame = tb.Frame(details_window, padding="10")
                    text_frame.pack(fill=tk.BOTH, expand=True)
                    
                    text_widget = tk.Text(text_frame, wrap=tk.WORD)
                    scrollbar = tb.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                    text_widget.configure(yscrollcommand=scrollbar.set)
                    
                    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                    
                    # 插入详细信息
                    text_widget.insert(tk.END, details)
                    text_widget.config(state=tk.DISABLED)
                    
                else:
                    messagebox.showerror("错误", f"无法获取 {package_name} 的详细信息")
                    
            except Exception as e:
                messagebox.showerror("错误", f"获取详细信息失败: {str(e)}")
        
        threading.Thread(target=get_details, daemon=True).start()
    
    def open_package_directory(self):
        """打开包的安装目录"""
        selection = self.packages_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个包")
            return
        
        package_name = self.packages_tree.item(selection[0], "text")
        location = self.packages_tree.item(selection[0], "values")[2]  # 安装位置
        
        if location and location != "未知":
            try:
                # 在Windows上使用explorer打开目录
                if os.name == 'nt':
                    os.startfile(location)
                else:
                    # 在其他系统上使用默认文件管理器
                    subprocess.run(['xdg-open', location])
                
                self.log_message(f"已打开 {package_name} 的安装目录: {location}")
            except Exception as e:
                messagebox.showerror("错误", f"无法打开目录: {str(e)}")
        else:
            messagebox.showwarning("警告", "无法获取包的安装位置")
    
    def uninstall_package(self):
        """卸载选中的包"""
        selection = self.packages_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个包")
            return
        
        package_name = self.packages_tree.item(selection[0], "text")
        
        # 确认卸载
        if not messagebox.askyesno("确认卸载", f"确定要卸载 {package_name} 吗？"):
            return
        
        def uninstall():
            self.log_message(f"开始卸载 {package_name}...")
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", package_name],
                                      capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    self.log_message(f"✓ {package_name} 卸载成功")
                    messagebox.showinfo("成功", f"{package_name} 卸载成功")
                    # 刷新包列表
                    self.check_installed_packages()
                else:
                    self.log_message(f"✗ {package_name} 卸载失败: {result.stderr}")
                    messagebox.showerror("错误", f"{package_name} 卸载失败")
                    
            except Exception as e:
                self.log_message(f"✗ {package_name} 卸载异常: {str(e)}")
                messagebox.showerror("错误", f"卸载异常: {str(e)}")
        
        threading.Thread(target=uninstall, daemon=True).start()

def main():
    if is_already_running():
        messagebox.showwarning("警告", "程序已经在运行中！")
        return
        
    try:
        root = tb.Window(themename="cosmo")
        app = JhHzApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("错误", f"程序发生错误: {str(e)}")

if __name__ == "__main__":
    main()