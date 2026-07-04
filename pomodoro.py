"""
Pomodoro Timer - 番茄钟应用
基于 Python + Tkinter 的专注计时工具

功能:
- 25分钟专注 / 5分钟短休息 / 15分钟长休息
- 自动切换阶段，支持手动跳过
- 完成计数统计
- 声音提醒
- 自定义时长配置
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import winsound
import threading
from datetime import datetime, timedelta


# ==================== 配置管理 ====================

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "work_duration": 25,       # 专注时长（分钟）
    "short_break": 5,          # 短休息时长（分钟）
    "long_break": 15,          # 长休息时长（分钟）
    "rounds_before_long": 4,   # 几次专注后长休息
    "auto_start_breaks": True, # 自动开始休息
    "auto_start_work": False,  # 自动开始专注
    "show_remaining": True,    # 显示剩余时间
    "sound_enabled": True,     # 启用声音
}


class ConfigManager:
    """配置管理器 - 持久化用户设置"""

    def __init__(self):
        self.config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                self.config.update(saved)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def get(self, key):
        return self.config.get(key, DEFAULT_CONFIG[key])

    def set(self, key, value):
        self.config[key] = value
        self.save()


# ==================== 定时器核心 ====================

class PomodoroTimer:
    """番茄钟定时器核心逻辑"""

    STATUS_WORK = "work"
    STATUS_BREAK = "break"
    STATUS_LONG_BREAK = "long_break"

    MODES = {
        STATUS_WORK: "专注",
        STATUS_BREAK: "短休息",
        STATUS_LONG_BREAK: "长休息",
    }

    def __init__(self, config: ConfigManager):
        self.config = config
        self._reset()

    def _reset(self):
        self.status = self.STATUS_WORK
        self.remaining_seconds = self.config.get("work_duration") * 60
        self.total_seconds = self.remaining_seconds
        self.completed_rounds = 0
        self.running = False
        self._thread = None

    def _get_duration(self):
        if self.status == self.STATUS_WORK:
            return self.config.get("work_duration") * 60
        elif self.status == self.STATUS_BREAK:
            return self.config.get("short_break") * 60
        else:
            return self.config.get("long_break") * 60

    def start(self):
        if self.running:
            return
        self.running = True
        self._tick()

    def pause(self):
        self.running = False

    def toggle(self):
        if self.running:
            self.pause()
        else:
            self.start()

    def reset(self):
        self.running = False
        self._reset()

    def skip(self):
        """跳过当前阶段，进入下一阶段"""
        self.running = False
        if self.status == self.STATUS_WORK:
            self.completed_rounds += 1
            self._switch_to_break()
        else:
            self._switch_to_work()

    def switch_to_short_break(self):
        self.running = False
        self.status = self.STATUS_BREAK
        duration = self._get_duration()
        self.remaining_seconds = duration
        self.total_seconds = duration

    def switch_to_long_break(self):
        self.running = False
        self.status = self.STATUS_LONG_BREAK
        duration = self._get_duration()
        self.remaining_seconds = duration
        self.total_seconds = duration

    def _tick(self):
        """定时器心跳 - 每1秒调用一次"""
        if not self.running:
            return

        self.remaining_seconds -= 1

        if self.remaining_seconds <= 0:
            self._on_complete()
            return

        self._thread = threading.Timer(1.0, self._tick)
        self._thread.daemon = True
        self._thread.start()

    def _on_complete(self):
        """阶段完成处理"""
        if self.status == self.STATUS_WORK:
            self.completed_rounds += 1
            self._play_sound()
            self._switch_to_break()
        else:
            self._play_sound()
            self._switch_to_work()

    def _switch_to_break(self):
        if self.completed_rounds % self.config.get("rounds_before_long") == 0:
            self.status = self.STATUS_LONG_BREAK
        else:
            self.status = self.STATUS_BREAK

        duration = self._get_duration()
        self.remaining_seconds = duration
        self.total_seconds = duration

        if self.config.get("auto_start_breaks"):
            self.start()

    def _switch_to_work(self):
        self.status = self.STATUS_WORK
        duration = self._get_duration()
        self.remaining_seconds = duration
        self.total_seconds = duration

        if self.config.get("auto_start_work"):
            self.start()

    def _play_sound(self):
        if self.config.get("sound_enabled"):
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def get_time_display(self):
        minutes, seconds = divmod(self.remaining_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def get_progress(self):
        if self.total_seconds == 0:
            return 0
        return 1.0 - (self.remaining_seconds / self.total_seconds)

    def get_status_label(self):
        return self.MODES[self.status]


# ==================== UI 主窗口 ====================

class PomodoroApp:
    """番茄钟主界面"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.config_mgr = ConfigManager()
        self.timer = PomodoroTimer(self.config_mgr)

        self._build_ui()
        self._update_display()
        self._setup_protocol()

    def _build_ui(self):
        """构建界面"""
        self.root.title("🍅 番茄钟")
        self.root.geometry("420x520")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        # --- 顶部标题 ---
        header_frame = tk.Frame(self.root, bg="#1a1a2e")
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 0))

        title = tk.Label(
            header_frame,
            text="🍅 番茄钟",
            font=("Segoe UI", 18, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
        )
        title.pack()

        # --- 模式标签 ---
        self.mode_label = tk.Label(
            header_frame,
            text=self.timer.get_status_label(),
            font=("Segoe UI", 12),
            fg="#a0a0b0",
            bg="#1a1a2e",
        )
        self.mode_label.pack(pady=(4, 0))

        # --- 进度环（Canvas绘制） ---
        ring_size = 220
        center = ring_size // 2
        radius = 90
        thickness = 10

        self.canvas = tk.Canvas(
            self.root,
            width=ring_size,
            height=ring_size,
            bg="#1a1a2e",
            highlightthickness=0,
        )
        self.canvas.pack(pady=(20, 10))

        # 背景圆环
        self.canvas.create_oval(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            outline="#2a2a4a",
            width=thickness,
        )

        # 进度弧
        self.progress_arc = self.canvas.create_arc(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            start=0,
            extent=0,
            outline="#e94560",
            width=thickness,
            style=tk.ARC,
        )

        # 时间文字
        self.time_label = tk.Label(
            self.canvas,
            text="25:00",
            font=("Segoe UI", 36, "bold"),
            fg="#ffffff",
            bg="#1a1a2e",
        )
        self.time_label_window = self.canvas.create_window(
            center, center - 5, window=self.time_label
        )

        # --- 控制按钮 ---
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(pady=(10, 0))

        # 主按钮（开始/暂停）
        self.main_btn = tk.Button(
            btn_frame,
            text="▶ 开始",
            font=("Segoe UI", 14, "bold"),
            fg="#ffffff",
            bg="#e94560",
            activebackground="#c73650",
            activeforeground="#ffffff",
            border=0,
            cursor="hand2",
            width=10,
            command=self._on_main_button,
        )
        self.main_btn.pack(side=tk.LEFT, padx=5)

        # 跳过按钮
        skip_btn = tk.Button(
            btn_frame,
            text="⏭ 跳过",
            font=("Segoe UI", 11),
            fg="#ffffff",
            bg="#2a2a4a",
            activebackground="#3a3a5a",
            activeforeground="#ffffff",
            border=0,
            cursor="hand2",
            command=self._on_skip,
        )
        skip_btn.pack(side=tk.LEFT, padx=5)

        # --- 休息切换按钮组 ---
        break_frame = tk.Frame(self.root, bg="#1a1a2e")
        break_frame.pack(pady=(0, 0))

        self.short_break_btn = tk.Button(
            break_frame,
            text="短休息",
            font=("Segoe UI", 10),
            fg="#a0a0b0",
            bg="#16213e",
            activebackground="#1a2a4a",
            activeforeground="#ffffff",
            border=0,
            cursor="hand2",
            command=self._on_switch_short_break,
        )
        self.short_break_btn.pack(side=tk.LEFT, padx=5)

        self.long_break_btn = tk.Button(
            break_frame,
            text="长休息",
            font=("Segoe UI", 10),
            fg="#a0a0b0",
            bg="#16213e",
            activebackground="#1a2a4a",
            activeforeground="#ffffff",
            border=0,
            cursor="hand2",
            command=self._on_switch_long_break,
        )
        self.long_break_btn.pack(side=tk.LEFT, padx=5)

        # --- 已完成计数 ---
        self.counter_label = tk.Label(
            self.root,
            text="🍅 已完成: 0 个番茄",
            font=("Segoe UI", 11),
            fg="#a0a0b0",
            bg="#1a1a2e",
        )
        self.counter_label.pack(pady=(20, 0))

        # --- 底部设置按钮 ---
        settings_btn = tk.Button(
            self.root,
            text="⚙ 设置",
            font=("Segoe UI", 10),
            fg="#a0a0b0",
            bg="#16213e",
            activebackground="#1a2a4a",
            activeforeground="#ffffff",
            border=0,
            cursor="hand2",
            command=self._open_settings,
        )
        settings_btn.pack(pady=(15, 0))

        # 保存初始状态用于进度环绘制
        self._center = center
        self._radius = radius

        # 初始化休息按钮状态
        self._update_break_buttons()

    def _on_main_button(self):
        if self.timer.running:
            self.timer.pause()
            self.main_btn.config(text="▶ 继续", bg="#0f3460")
        else:
            self.timer.start()
            self.main_btn.config(text="⏸ 暂停", bg="#0f3460")
        self._schedule_update()

    def _on_reset(self):
        self.timer.reset()
        self.main_btn.config(text="▶ 开始", bg="#e94560")
        self._update_break_buttons()
        self._update_display()

    def _on_skip(self):
        self.timer.skip()
        self._update_break_buttons()
        self._schedule_update()

    def _on_switch_short_break(self):
        self.timer.switch_to_short_break()
        self._update_break_buttons()
        self._schedule_update()

    def _on_switch_long_break(self):
        self.timer.switch_to_long_break()
        self._update_break_buttons()
        self._schedule_update()

    def _update_break_buttons(self):
        """更新休息切换按钮的高亮状态"""
        active_color = "#e94560"
        inactive_color = "#16213e"
        inactive_fg = "#a0a0b0"
        active_fg = "#ffffff"

        if self.timer.status == self.timer.STATUS_BREAK:
            self.short_break_btn.config(bg=active_color, fg=active_fg)
        else:
            self.short_break_btn.config(bg=inactive_color, fg=inactive_fg)

        if self.timer.status == self.timer.STATUS_LONG_BREAK:
            self.long_break_btn.config(bg=active_color, fg=active_fg)
        else:
            self.long_break_btn.config(bg=inactive_color, fg=inactive_fg)

    def _schedule_update(self):
        """安排下一次UI更新"""
        if self.timer.running:
            self.root.after(250, self._update_display)

    def _update_display(self):
        """更新界面显示"""
        # 更新时间文字
        self.time_label.config(text=self.timer.get_time_display())

        # 更新进度环
        progress = self.timer.get_progress()
        extent = progress * 270  # 270度圆弧
        self.canvas.itemconfig(self.progress_arc, extent=extent)

        # 根据模式改变颜色
        if self.timer.status == self.timer.STATUS_WORK:
            color = "#e94560"  # 红色 - 专注
        else:
            color = "#0f3460"  # 蓝色 - 休息
        self.canvas.itemconfig(self.progress_arc, outline=color)
        self.main_btn.config(bg=color)

        # 更新模式标签
        self.mode_label.config(text=self.timer.get_status_label())
        self._update_break_buttons()

        # 更新计数器
        self.counter_label.config(text=f"🍅 已完成: {self.timer.completed_rounds} 个番茄")

        # 更新按钮文本
        if self.timer.running:
            self.main_btn.config(text="⏸ 暂停")
        else:
            if self.timer.remaining_seconds == self.timer.total_seconds:
                self.main_btn.config(text="▶ 开始")
            else:
                self.main_btn.config(text="▶ 继续")

        # 持续调度
        if self.timer.running:
            self.root.after(250, self._update_display)

    def _open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self.root, self.config_mgr)
        self.root.wait_window(dialog.window)
        # 重新加载配置
        self.timer = PomodoroTimer(self.config_mgr)
        self._update_display()

    def _setup_protocol(self):
        """设置窗口关闭协议"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.timer.running = False
        self.root.destroy()


# ==================== 设置对话框 ====================

class SettingsDialog:
    """设置对话框"""

    def __init__(self, parent, config_mgr: ConfigManager):
        self.config_mgr = config_mgr
        self.window = tk.Toplevel(parent)
        self.window.title("⚙ 设置")
        self.window.geometry("380x480")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg="#1a1a2e")

        # 居中
        x = parent.winfo_x() + (parent.winfo_width() - 380) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 480) // 2
        self.window.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        form_frame = tk.Frame(self.window, bg="#1a1a2e")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # 专注时长
        self._add_setting_row(
            form_frame, "专注时长 (分钟)", "work_duration", 1, 120
        )
        # 短休息
        self._add_setting_row(form_frame, "短休息 (分钟)", "short_break", 1, 30)
        # 长休息
        self._add_setting_row(form_frame, "长休息 (分钟)", "long_break", 1, 60)
        # 轮次
        self._add_setting_row(
            form_frame, "长休息间隔 (个番茄)", "rounds_before_long", 1, 10
        )

        # 开关选项
        self.auto_break_var = tk.BooleanVar(
            value=self.config_mgr.get("auto_start_breaks")
        )
        tk.Checkbutton(
            form_frame,
            text="休息时自动开始",
            variable=self.auto_break_var,
            bg="#1a1a2e",
            fg="#ffffff",
            selectcolor="#16213e",
            command=self._save_bool,
        ).pack(anchor=tk.W, pady=(5, 0))

        self.auto_work_var = tk.BooleanVar(
            value=self.config_mgr.get("auto_start_work")
        )
        tk.Checkbutton(
            form_frame,
            text="专注时自动开始",
            variable=self.auto_work_var,
            bg="#1a1a2e",
            fg="#ffffff",
            selectcolor="#16213e",
            command=self._save_bool,
        ).pack(anchor=tk.W)

        self.sound_var = tk.BooleanVar(value=self.config_mgr.get("sound_enabled"))
        tk.Checkbutton(
            form_frame,
            text="启用提示音",
            variable=self.sound_var,
            bg="#1a1a2e",
            fg="#ffffff",
            selectcolor="#16213e",
            command=self._save_bool,
        ).pack(anchor=tk.W, pady=(5, 0))

        # 保存按钮
        save_btn = tk.Button(
            form_frame,
            text="保存",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg="#e94560",
            activebackground="#c73650",
            border=0,
            cursor="hand2",
            width=15,
            command=self._save_and_close,
        )
        save_btn.pack(pady=(20, 0))

    def _add_setting_row(self, parent, label_text, key, min_val, max_val):
        row = tk.Frame(parent, bg="#1a1a2e")
        row.pack(fill=tk.X, pady=4)

        tk.Label(
            row, text=label_text, font=("Segoe UI", 10), fg="#a0a0b0", bg="#1a1a2e"
        ).pack(side=tk.LEFT, padx=(0, 10))

        var = tk.IntVar(value=self.config_mgr.get(key))
        entry = tk.Entry(
            row,
            textvariable=var,
            font=("Segoe UI", 10),
            fg="#ffffff",
            bg="#2a2a4a",
            bd=0,
            width=6,
            justify="center",
        )
        entry.pack(side=tk.RIGHT)

        # 范围限制
        def on_change(*_):
            val = var.get()
            val = max(min_val, min(max_val, val))
            var.set(val)
            self.config_mgr.set(key, val)

        var.trace_add("write", on_change)

    def _save_bool(self):
        self.config_mgr.set("auto_start_breaks", self.auto_break_var.get())
        self.config_mgr.set("auto_start_work", self.auto_work_var.get())
        self.config_mgr.set("sound_enabled", self.sound_var.get())

    def _save_and_close(self):
        self.window.destroy()


# ==================== 入口 ====================

def main():
    root = tk.Tk()
    app = PomodoroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
