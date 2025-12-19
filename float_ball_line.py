import sys
import os
import subprocess
import math
import json
import time
import threading

# 使用环境变量抑制PyQt5的警告
os.environ['QT_LOGGING_RULES'] = '*.warning=false;*.critical=false'

# 更直接地抑制所有DeprecationWarning
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 首先导入Qt核心模块，确保在创建QApplication前设置高DPI属性
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

# 设置高DPI缩放属性，必须在创建QApplication之前设置
sys.argv += ['--no-sandbox']
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# 导入其他模块
import cv2
import numpy as np
from PyQt5.QtWidgets import (QWidget, QLabel, QDesktopWidget, QMainWindow,
                              QLineEdit, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QTextEdit, QMenu, QAction)
from PyQt5.QtCore import QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, pyqtSignal, QObject, Qt
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QPen, QColor, QGuiApplication, QScreen, QIcon, QRegion

# 尝试导入markdown库，如果没有则使用简单的文本格式
markdown_available = False
try:
    import markdown
    markdown_available = True
except ImportError:
    print("未找到markdown库，将使用纯文本显示。请安装markdown库以支持markdown格式。")

# 用于进程间通信的文件路径
INPUT_FILE = "data/input_message.json"
OUTPUT_FILE = "data/output_message.json"
# 用于控制悬浮球输入框禁用状态的标志文件路径
INPUT_DISABLE_FLAG = "data/input_disabled.flag"

class BackendServiceListener(QObject):
    """消息通信器，负责与test_float.py进行通信"""
    response_received = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.listener_thread = None
        self.last_output_time = 0
        self.current_request_id = None
    
    def start(self):
        """启动通信器"""
        self.running = True
        self.listener_thread = threading.Thread(target=self.listen_for_responses)
        self.listener_thread.daemon = True
        self.listener_thread.start()
    
    def stop(self):
        """停止通信器"""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=1.0)
    
    def send_message(self, message, screenshot_filename=None):
        """发送消息到test_float.py"""
        try:
            # 确保数据目录存在
            if not os.path.exists("data"):
                os.makedirs("data")
            
            # 创建请求ID
            request_id = str(time.time())
            self.current_request_id = request_id
            
            # 构建消息数据
            data = {
                'request_id': request_id,
                'content': message,
                'timestamp': time.time()
            }
            
            # 添加缩略图文件名（如果有）
            if screenshot_filename:
                data['screenshot_filename'] = screenshot_filename
                print(f"缩略图文件名已添加: {screenshot_filename}")
            
            # 写入输入文件
            with open(INPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            print(f"消息已发送: {message}")
            return True
        except Exception as e:
            print(f"发送消息失败: {e}")
            return False
    
    def listen_for_responses(self):
        """监听test_float.py的响应，任何时候OUTPUT_FILE内容被修改都会显示"""
        while self.running:
            try:
                # 检查输出文件是否存在且有更新
                if os.path.exists(OUTPUT_FILE):
                    file_time = os.path.getmtime(OUTPUT_FILE)
                    if file_time > self.last_output_time:
                        # 读取响应消息
                        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # 直接获取content，不检查request_id，确保任何修改都能显示
                        response = data.get('content', '')
                        if response:  # 确保内容不为空
                            print(f"检测到OUTPUT_FILE更新，显示内容: {response}")
                            # 通过信号发送响应
                            self.response_received.emit(response)
                        
                        # 记录最后读取时间
                        self.last_output_time = file_time
            
            except Exception as e:
                print(f"监听响应时出错: {e}")
            
            # 短暂休眠，减少CPU占用
            time.sleep(0.1)

# 创建全局消息通信器实例
comm_manager = BackendServiceListener()

class MouseGestureVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.screen_geometry = None

    def set_screen(self, screen_geometry):
        self.screen_geometry = screen_geometry
        self.setGeometry(screen_geometry)

    def update_trajectory(self, points):
        self.trajectory_points = points[:]
        self.update()

    def paintEvent(self, event):
        if not hasattr(self, 'trajectory_points') or not self.trajectory_points:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if len(self.trajectory_points) > 1:
            total_points = len(self.trajectory_points)
            for i in range(total_points - 1):
                age_ratio = i / (total_points - 1)
                alpha = int(255 * (1 - age_ratio * 0.7))
                pen = QPen(QColor(30, 144, 255, alpha), 4)
                painter.setPen(pen)
                if self.screen_geometry:
                    p1 = QPoint(self.trajectory_points[i].x() - self.screen_geometry.x(),
                                self.trajectory_points[i].y() - self.screen_geometry.y())
                    p2 = QPoint(self.trajectory_points[i + 1].x() - self.screen_geometry.x(),
                                self.trajectory_points[i + 1].y() - self.screen_geometry.y())
                    painter.drawLine(p1, p2)


class ImagePreviewThumbnail(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.parent_input = parent
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 创建图片标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: rgba(68, 68, 68, 0.9); border-radius: 4px;")

        # 创建删除按钮
        self.delete_btn = QPushButton()
        self.delete_btn.setFixedSize(16, 16)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """)
        self.delete_btn.setText("×")
        self.delete_btn.clicked.connect(self.delete_thumbnail)

        layout.addWidget(self.image_label, alignment=Qt.AlignLeft)
        layout.addWidget(self.delete_btn, alignment=Qt.AlignTop)
        self.setLayout(layout)

        # 加载并缩放图片
        self.load_and_scale_image()

    def load_and_scale_image(self):
        if os.path.exists(self.image_path):
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                # 获取输入框宽度作为参考
                max_size = self.parent_input.width() // 2

                # 计算缩放比例
                width = pixmap.width()
                height = pixmap.height()

                if width > height:
                    if width > max_size:
                        scale = max_size / width
                        new_width = max_size
                        new_height = int(height * scale)
                    else:
                        new_width = width
                        new_height = height
                else:
                    if height > max_size:
                        scale = max_size / height
                        new_height = max_size
                        new_width = int(width * scale)
                    else:
                        new_width = width
                        new_height = height

                scaled_pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
                self.setFixedSize(new_width + 20, new_height)  # +20 为删除按钮留出空间

    def delete_thumbnail(self):
        # 删除缩略图和对应的图片文件
        if os.path.exists(self.image_path):
            try:
                os.remove(self.image_path)
                print(f"图片已删除: {self.image_path}")
            except Exception as e:
                print(f"删除图片时出错: {e}")

        # 通知父窗口更新状态
        if self.parent_input and hasattr(self.parent_input, 'thumbnail_deleted'):
            self.parent_input.thumbnail_deleted()

        self.hide()
        self.deleteLater()


class ChatInputBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.screenshot_thumbnail = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("美观输入框")
        base_width, base_height = 280, 40
        scaled_width, scaled_height = self.get_scaled_size(base_width, base_height)
        self.setGeometry(0, 0, scaled_width, scaled_height)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        input_container = QFrame()
        scaled_radius, scaled_padding = self.get_scaled_size(8, 6)
        input_container.setStyleSheet(f"""
            QFrame {{
                background-color: #333;
                border-radius: {scaled_radius}px;
                padding: {scaled_padding}px;
                margin: {self.get_scaled_size(5, 5)[0]}px;
            }}
        """)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(self.get_scaled_size(4, 4)[0])

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("与 Open Assistant 交流")
        scaled_border_radius = self.get_scaled_size(4, 4)[0]
        scaled_padding_lr, scaled_padding_tb = self.get_scaled_size(6, 4)
        input_font_size = self.get_scaled_font_size(12)
        self.input_line.setStyleSheet(f"""
            QLineEdit {{
                background-color: #444;
                border: 1px solid #666;
                border-radius: {scaled_border_radius}px;
                padding: {scaled_padding_tb}px {scaled_padding_lr}px;
                color: white;
                font-size: {input_font_size}px;
            }}
            QLineEdit:focus {{
                border-color: #0078d4;
                outline: none;
            }}
        """)
        self.input_line.returnPressed.connect(self.handle_return_pressed)

        input_layout.addWidget(self.input_line)
        input_container.setLayout(input_layout)
        layout.addWidget(input_container)
        self.setLayout(layout)

    def get_scaled_size(self, base_width, base_height):
        if self.parent():
            try:
                parent = self.parent()
                current_screen = parent.screen() if hasattr(parent, 'screen') else None
                if not current_screen and hasattr(parent, 'get_current_screen'):
                    screen_rect = parent.get_current_screen()
                    for screen in QApplication.screens():
                        if screen.geometry() == screen_rect:
                            current_screen = screen
                            break
                if not current_screen:
                    current_screen = QApplication.primaryScreen()
                if current_screen:
                    scale_factor = current_screen.logicalDotsPerInch() / 96.0
                    return int(base_width * scale_factor), int(base_height * scale_factor)
            except Exception as e:
                print(f"Error getting scaled size: {e}")
        return base_width, base_height

    def get_scaled_font_size(self, base_size):
        if self.parent():
            try:
                parent = self.parent()
                current_screen = parent.screen() if hasattr(parent, 'screen') else None
                if not current_screen and hasattr(parent, 'get_current_screen'):
                    screen_rect = parent.get_current_screen()
                    for screen in QApplication.screens():
                        if screen.geometry() == screen_rect:
                            current_screen = screen
                            break
                if not current_screen:
                    current_screen = QApplication.primaryScreen()
                if current_screen:
                    scale_factor = current_screen.logicalDotsPerInch() / 96.0
                    return int(base_size * scale_factor)
            except Exception as e:
                print(f"Error getting scaled font size: {e}")
        return base_size

    def hide_input(self):
        self.hide()
        # 同时隐藏缩略图
        self.hide_thumbnail()
        if self.parent():
            self.parent().is_input_visible = False
            self.parent().is_hovered_on_input = False

    def hide_thumbnail(self):
        if self.screenshot_thumbnail:
            self.screenshot_thumbnail.hide()
            self.screenshot_thumbnail.deleteLater()
            self.screenshot_thumbnail = None

    def set_scaled_geometry(self, x, y):
        if self.parent():
            current_screen = self.parent().get_current_screen()
            if current_screen:
                self.move(x, y)
                # 调整缩略图位置
                if self.screenshot_thumbnail:
                    thumbnail_y = y + self.height() + 5  # 输入框下方5像素
                    self.screenshot_thumbnail.move(x, thumbnail_y)
                return
        self.move(x, y)

    def handle_return_pressed(self):
        # 检查输入是否被禁用
        if os.path.exists(INPUT_DISABLE_FLAG):
            # 显示禁用提示
            if self.parent() and hasattr(self.parent(), 'display_widget') and self.parent().display_widget:
                self.parent().display_widget.waiting_input_label.setText("语音模式下禁用输入")
                self.parent().display_widget.show_waiting_message()
            return
            
        # 检查父窗口是否处于等待状态
        if self.parent() and hasattr(self.parent(), 'is_waiting') and self.parent().is_waiting:
            # 显示等待提示
            if self.parent() and hasattr(self.parent(), 'display_widget') and self.parent().display_widget:
                self.parent().display_widget.show_waiting_message()
            return

        text = self.input_line.text()
        if text:
            if self.parent() and hasattr(self.parent(), 'display_widget') and self.parent().display_widget:
                self.parent().display_widget.show_message(text)
                # 设置父窗口为等待状态
                if self.parent():
                    self.parent().is_waiting = True
                
                # 检查是否有缩略图，并获取文件名
                screenshot_filename = None
                if hasattr(self, 'screenshot_thumbnail') and self.screenshot_thumbnail:
                    # 假设缩略图有image_path属性存储文件路径
                    if hasattr(self.screenshot_thumbnail, 'image_path'):
                        screenshot_filename = os.path.basename(self.screenshot_thumbnail.image_path)
                        print(f"找到缩略图文件: {screenshot_filename}")
                        
                        # 复制截图到test.png并删除原test2.png
                        original_path = self.screenshot_thumbnail.image_path
                        if original_path == "imgs/test2.png":
                            try:
                                # 确保imgs目录存在
                                if not os.path.exists("imgs"):
                                    os.makedirs("imgs")
                                
                                # 复制图片到test.png
                                import shutil
                                new_path = "imgs/test.png"
                                shutil.copy2(original_path, new_path)
                                print(f"图片已复制到: {new_path}")
                                
                                # 删除原图片
                                if os.path.exists(original_path):
                                    os.remove(original_path)
                                    print(f"原图片已删除: {original_path}")
                                    
                                    # 更新文件名
                                    screenshot_filename = "test.png"
                            except Exception as e:
                                print(f"处理图片时出错: {e}")
                
                # 通过通信管理器发送消息，包含缩略图文件名
                comm_manager.send_message(text, screenshot_filename)
                
                # 发送消息后隐藏缩略图
                self.hide_thumbnail()
            self.input_line.clear()

    # def write_text_to_file(self, text):
    #     try:
    #         if not os.path.exists("data"):
    #             os.makedirs("data")
    #         with open("user_content_text.txt", "a", encoding="utf-8") as f:
    #             f.write(text + "\n")
    #         print(f"文字已写入文件: {text}")
    #     except Exception as e:
    #         print(f"写入文件时出错: {e}")

    def show_screenshot_thumbnail(self, image_path):
        # 如果已有缩略图，先删除
        self.hide_thumbnail()

        # 创建新的缩略图
        self.screenshot_thumbnail = ImagePreviewThumbnail(image_path, self)
        # 放置在输入框下方
        input_pos = self.pos()
        thumbnail_x = input_pos.x()
        thumbnail_y = input_pos.y() + self.height() + 5  # 输入框下方5像素
        self.screenshot_thumbnail.move(thumbnail_x, thumbnail_y)
        self.screenshot_thumbnail.show()

    def thumbnail_deleted(self):
        # 通知父窗口截图已删除
        if self.parent() and hasattr(self.parent(), 'on_thumbnail_deleted'):
            self.parent().on_thumbnail_deleted()
        self.screenshot_thumbnail = None


class ChatDisplayBox(QWidget):
    def __init__(self, parent=None, saved_content=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.display_text = saved_content  # 初始化时使用保存的内容
        # 高度调整相关变量
        self.is_resizing = False
        self.resize_start_y = 0
        self.min_height = 100  # 最小高度限制
        self.init_ui()
        # 连接通信器的响应信号
        comm_manager.response_received.connect(self.on_response_received)


    def init_ui(self):
        self.setWindowTitle("显示框")
        base_width, base_height = 280, 200
        scaled_width, scaled_height = self.get_scaled_size(base_width, base_height)
        self.setGeometry(0, 0, scaled_width, scaled_height)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        display_container = QFrame()
        scaled_radius, scaled_padding = self.get_scaled_size(8, 6)
        display_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2c3e50; /* Dark blue-grey background */
                border-radius: {scaled_radius}px;
                padding: 0px; /* No padding on container */
                margin: {self.get_scaled_size(5, 5)[0]}px;
                border: 1px solid #34495e;
            }}
        """)

        # 使用QTextEdit支持文本选择和复制
        self.display_text_edit = QTextEdit()
        self.display_text_edit.setReadOnly(True)  # 设置为只读
        self.display_text_edit.setUndoRedoEnabled(False)
        scaled_border_radius = self.get_scaled_size(4, 4)[0]
        scaled_padding_lr, scaled_padding_tb = self.get_scaled_size(6, 4)
        input_font_size = self.get_scaled_font_size(12)
        self.display_text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent; /* Transparent background */
                border: none; /* No border on the text edit itself */
                padding: 0px;
                color: #ecf0f1; /* Match body text color */
                font-size: {input_font_size}px;
            }}
        """)
        self.display_text_edit.setWordWrapMode(True)
        self.display_text_edit.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        # 启用HTML支持以显示markdown
        self.display_text_edit.setAcceptRichText(True)

        # 初始化时设置保存的内容
        if self.display_text:
            self.set_display_content(self.display_text)
        else:
            self.display_text_edit.clear()

        self.waiting_label = QLabel("等待中...\n请快速将鼠标移动到被控窗口并单击😁")
        self.waiting_label.setStyleSheet(f"""
            QLabel {{
                background-color: #444;
                border: 1px solid #666;
                border-radius: {self.get_scaled_size(4, 4)[0]}px;
                padding: {self.get_scaled_size(6, 4)[1]}px {self.get_scaled_size(6, 4)[0]}px;
                color: white;
                font-size: {self.get_scaled_font_size(12)}px;
            }}
        """)
        self.waiting_label.setAlignment(Qt.AlignCenter)
        self.waiting_label.hide()

        # 等待提示标签
        self.waiting_input_label = QLabel("等待时不能上传指令")
        self.waiting_input_label.setStyleSheet(f"""
            QLabel {{
                background-color: #444;
                border: 1px solid #ff4444;
                border-radius: {self.get_scaled_size(4, 4)[0]}px;
                padding: {self.get_scaled_size(6, 4)[1]}px {self.get_scaled_size(6, 4)[0]}px;
                color: #ff4444;
                font-size: {self.get_scaled_font_size(12)}px;
            }}
        """)
        self.waiting_input_label.setAlignment(Qt.AlignCenter)
        self.waiting_input_label.hide()

        layout.addWidget(self.display_text_edit)
        layout.addWidget(self.waiting_label)
        layout.addWidget(self.waiting_input_label)
        display_container.setLayout(layout)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(display_container)
        self.setLayout(main_layout)

    def get_scaled_size(self, base_width, base_height):
        if self.parent():
            try:
                parent = self.parent()
                current_screen = parent.screen() if hasattr(parent, 'screen') else None
                if not current_screen and hasattr(parent, 'get_current_screen'):
                    screen_rect = parent.get_current_screen()
                    for screen in QApplication.screens():
                        if screen.geometry() == screen_rect:
                            current_screen = screen
                            break
                if not current_screen:
                    current_screen = QApplication.primaryScreen()
                if current_screen:
                    scale_factor = current_screen.logicalDotsPerInch() / 96.0
                    return int(base_width * scale_factor), int(base_height * scale_factor)
            except Exception as e:
                print(f"Error getting scaled size: {e}")
        return base_width, base_height

    def get_scaled_font_size(self, base_size):
        if self.parent():
            try:
                parent = self.parent()
                current_screen = parent.screen() if hasattr(parent, 'screen') else None
                if not current_screen and hasattr(parent, 'get_current_screen'):
                    screen_rect = parent.get_current_screen()
                    for screen in QApplication.screens():
                        if screen.geometry() == screen_rect:
                            current_screen = screen
                            break
                if not current_screen:
                    current_screen = QApplication.primaryScreen()
                if current_screen:
                    scale_factor = current_screen.logicalDotsPerInch() / 96.0
                    return int(base_size * scale_factor)
            except Exception as e:
                print(f"Error getting scaled font size: {e}")
        return base_size

    def show_message(self, text):
        self.display_text = text
        self.display_text_edit.setText(text)
        self.display_text_edit.hide()
        self.waiting_label.setText("等待中...\n请快速将鼠标移动到被控窗口并单击😁")
        self.waiting_label.show()
        self.waiting_input_label.hide()
        #self.wait_timer.start(5000)  # 5秒后显示回答

    def set_display_content(self, text):
        """设置显示内容，支持markdown格式和聊天气泡"""
        self.display_text = text
        
        # 创建禁用输入标志文件，确保显示内容后2秒内无法输入
        try:
            with open(INPUT_DISABLE_FLAG, 'w') as f:
                f.write('')
            print(f"已创建输入禁用标志，2秒内无法输入")
            
            # 设置2秒后自动删除标志文件，恢复输入功能
            QTimer.singleShot(2000, self.remove_disable_flag)
            
        except Exception as e:
            print(f"设置输入禁用标志失败: {e}")
            
        # --- NEW CHAT BUBBLE LOGIC ---
        user_text = ""
        ai_text = ""
        try:
            # 解析 "user: ... AI: ..." 格式的文本
            parts = text.split("\n\nAI:\n\n")
            user_part = parts[0]
            if user_part.startswith("user: "):
                user_text = user_part.replace("user: ", "", 1).strip()

            if len(parts) > 1:
                ai_text = parts[1].strip()
        except Exception:
            # 如果解析失败，将全部内容视为AI消息
            user_text = ""
            ai_text = text

        # 如果AI部分包含Markdown，则转换为HTML
        if markdown_available:
            ai_html = markdown.markdown(ai_text)
        else:
            # 否则，简单地将换行符替换为<br>
            ai_html = ai_text.replace("\n", "<br>")

        # 为用户文本进行HTML转义，防止内容被误解析为HTML标签
        import html
        user_html = html.escape(user_text)

        # 创建包含聊天气泡样式的完整HTML
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    background-color: #2c3e50; /* 深蓝灰色背景 */
                    color: #ecf0f1; /* 浅灰色文字 */
                    font-family: "Segoe UI", Arial, sans-serif;
                    font-size: 14px;
                    margin: 0;
                    padding: 10px;
                }}
                .bubble-container {{
                    display: flex;
                    flex-direction: column;
                }}
                .bubble {{
                    padding: 10px 15px;
                    border-radius: 18px;
                    margin-bottom: 8px;
                    max-width: 85%;
                    word-wrap: break-word; /* 自动换行 */
                }}
                .user-bubble {{
                    background-color: #2980b9; /* 稍亮的蓝色 */
                    color: white;
                    border-bottom-right-radius: 4px; /* 直角过渡效果 */
                    align-self: flex-end; /* 右对齐 */
                }}
                .ai-bubble {{
                    background-color: #34495e; /* 深邃的蓝灰色 */
                    color: #ecf0f1;
                    border-bottom-left-radius: 4px; /* 直角过渡效果 */
                    align-self: flex-start; /* 左对齐 */
                }}
                /* AI气泡内Markdown元素的基础样式 */
                .ai-bubble h1, .ai-bubble h2, .ai-bubble h3 {{
                    color: #ecf0f1;
                    margin-top: 5px;
                    margin-bottom: 10px;
                    border-bottom: 1px solid #2c3e50;
                    padding-bottom: 5px;
                }}
                .ai-bubble p {{ margin: 5px 0; }}
                .ai-bubble code {{
                    background-color: #2c3e50;
                    padding: 2px 5px;
                    border-radius: 4px;
                    font-family: "Courier New", monospace;
                }}
                .ai-bubble pre {{
                    background-color: #2c3e50;
                    padding: 10px;
                    border-radius: 5px;
                    overflow-x: auto;
                    border: 1px solid #34495e;
                }}
            </style>
        </head>
        <body>
            <div class="bubble-container">
                <div class="bubble user-bubble">{user_html}</div>
                <div class="bubble ai-bubble">{ai_html}</div>
            </div>
        </body>
        </html>
        """
        self.display_text_edit.setHtml(styled_html)
        # --- END OF NEW LOGIC ---
    
    def on_response_received(self, response_text):
        # 收到响应时显示
        self.display_text = response_text
        self.waiting_label.hide()
        self.set_display_content(response_text)
        self.display_text_edit.show()
        # 通知父窗口等待状态结束
        if self.parent() and hasattr(self.parent(), 'set_waiting_state'):
            self.parent().set_waiting_state(False)
            # 将内容保存到父窗口
            self.parent().saved_display_content = response_text

    def show_waiting_message(self):
        self.waiting_input_label.show()
        QTimer.singleShot(2000, self.hide_waiting_message)

    def hide_waiting_message(self):
        self.waiting_input_label.hide()
    
    def remove_disable_flag(self):
        """删除输入禁用标志文件，恢复输入功能"""
        try:
            if os.path.exists(INPUT_DISABLE_FLAG):
                os.remove(INPUT_DISABLE_FLAG)
                print("已删除输入禁用标志，恢复输入功能")
                # 隐藏等待消息标签
                if hasattr(self, 'waiting_input_label'):
                    self.waiting_input_label.hide()
        except Exception as e:
            print(f"删除输入禁用标志失败: {e}")

    def mousePressEvent(self, event):
        # 检查是否点击了窗口顶部边缘用于调整高度
        if event.button() == Qt.LeftButton and event.pos().y() <= 10:
            self.is_resizing = True
            self.resize_start_y = event.globalY()
            self.setCursor(Qt.SizeVerCursor)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        # 处理高度调整
        if self.is_resizing:
            current_y = event.globalY()
            delta = self.resize_start_y - current_y
            new_height = self.height() + delta
            
            # 确保高度不小于最小值
            if new_height >= self.min_height:
                self.resize(self.width(), new_height)
                self.resize_start_y = current_y
                
                # 调整显示文本框的大小
                self.display_text_edit.setMinimumHeight(new_height - 40)
                
                # 更新父窗口中的位置信息
                if self.parent() and hasattr(self.parent(), 'update_display_position'):
                    self.parent().update_display_position()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        # 结束调整大小
        if self.is_resizing:
            self.is_resizing = False
            self.setCursor(Qt.ArrowCursor)
            # 保存高度到父窗口
            if self.parent() and hasattr(self.parent(), 'saved_display_height'):
                self.parent().saved_display_height = self.height()
        super().mouseReleaseEvent(event)
    
    def hide_display(self):
        self.hide()
        if self.parent():
            self.parent().is_display_visible = False
            # 隐藏时保存内容到父窗口
            self.parent().saved_display_content = self.display_text


class AssistantAvatar(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_hover_effects()
        self.setup_context_menu()  # 添加右键菜单设置
        self.move_to_corner()
        self.dragging = False
        self.drag_position = QPoint()
        self.trajectory_points = []
        self.trajectory_window = MouseGestureVisualizer()
        self.current_screen = None
        self.saved_display_content = ""  # 用于保存显示框内容的变量
        self.saved_display_height = None  # 用于保存显示框高度的变量
        self.input_widget = ChatInputBox(self)
        self.display_widget = ChatDisplayBox(self)
        self.is_input_visible = False
        self.is_display_visible = False
        self.is_hovered_on_input = False
        self.is_hovered_on_display = False
        self.is_hovered = False
        self.last_screen_geometry = None
        self.leave_check_timer = QTimer()
        self.leave_check_timer.setSingleShot(True)
        self.leave_check_timer.timeout.connect(self.check_mouse_leave)
        self.is_waiting = False  # 等待状态标记
        self.screenshot_path = None  # 保存当前截图路径
        # 边缘隐藏相关属性
        self.is_hidden = False  # 悬浮球是否隐藏在边缘
        self.edge_margin = 10  # 边缘检测的像素范围
        self.hidden_width = 8  # 隐藏时显示的宽度，增加可见性

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NativeWindow)
        self.small_size = 50
        self.large_size = 50
        self.current_size = self.small_size
        self.setGeometry(0, 0, self.small_size, self.small_size)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        # 隐藏时的透明蓝色背景标签 - 使用更醒目的颜色和更高的透明度
        self.edge_label = QLabel(self)
        self.edge_label.setGeometry(0, 0, 0, 0)
        self.edge_label.setStyleSheet("background-color: rgba(0, 120, 215, 180); border-radius: 2px;")
        self.edge_label.hide()
        # 为边缘标签添加鼠标跟踪
        self.edge_label.setMouseTracking(True)
        self.load_image()
        
        # Apply circular mask
        mask = QRegion(self.rect(), QRegion.Ellipse)
        self.setMask(mask)
        
        self.show()

    def load_image(self):
        img_path = "downloads/圆AI.png"
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                self.original_pixmap = pixmap
                self.small_pixmap = self.original_pixmap.scaled(
                    self.small_size, self.small_size,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.label.setPixmap(self.small_pixmap)
                self.label.setGeometry(0, 0, self.small_size, self.small_size)
                return
        self.create_default_circle()

    def create_default_circle(self):
        size = max(self.small_size, self.large_size)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(0, 120, 215)))
        painter.setPen(QPen(QColor(0, 120, 215), 2))
        painter.drawEllipse(0, 0, size - 1, size - 1)
        painter.end()
        self.original_pixmap = pixmap
        self.small_pixmap = self.original_pixmap.scaled(
            self.small_size, self.small_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.label.setPixmap(self.small_pixmap)
        self.label.setGeometry(0, 0, self.small_size, self.small_size)

    def setup_hover_effects(self):
        self.setMouseTracking(True)
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutBack)

    def enterEvent(self, event):
        # 当鼠标进入边缘标签时恢复悬浮球
        if self.is_hidden:
            self.restore_from_edge()
        self.leave_check_timer.stop()
        current_screen = self.get_current_screen()
        if self.last_screen_geometry is None or self.last_screen_geometry != current_screen:
            self.last_screen_geometry = current_screen
            if self.input_widget:
                self.input_widget.hide()
            if self.display_widget:
                self.display_widget.hide()
            self.input_widget = ChatInputBox(self)
            # 重新创建显示框时传入保存的内容
            self.display_widget = ChatDisplayBox(self, self.saved_display_content)
            self.is_input_visible = False
            self.is_display_visible = False
            self.is_hovered_on_input = False
            self.is_hovered_on_display = False
        if not self.is_hovered:
            self.is_hovered = True
            self.animate_to_large()
            self.show_input_components()

    def leaveEvent(self, event):
        # 只有在非隐藏状态下才启动离开检查
        if not self.is_hidden:
            self.leave_check_timer.start(50)

    def check_mouse_leave(self):
        # 检查鼠标是否离开所有相关组件
        if not self.underMouse() and \
                not (self.input_widget and self.input_widget.underMouse()) and \
                not (self.display_widget and self.display_widget.underMouse()) and \
                not (self.input_widget and self.input_widget.screenshot_thumbnail and
                     self.input_widget.screenshot_thumbnail.underMouse()):
            
            self.is_hovered = False
            self.animate_to_small()
            
            # 只有当输入框和输入行都没有焦点时才隐藏
            if self.input_widget and not self.input_widget.hasFocus() and not self.input_widget.input_line.hasFocus():
                # 隐藏前保存显示内容
                if self.display_widget:
                    self.saved_display_content = self.display_widget.display_text
                
                # 关键修改：明确删除缩略图
                if self.input_widget:
                    self.input_widget.hide_thumbnail()
                
                # 隐藏输入框和显示框
                self.input_widget.hide()
                self.display_widget.hide()
                
                # 更新状态变量
                self.is_input_visible = False
                self.is_display_visible = False
                self.is_hovered_on_input = False
                self.is_hovered_on_display = False
                
                # 检查是否需要隐藏到边缘
                self.check_and_hide_to_edge()

    def on_input_hover_enter(self):
        self.leave_check_timer.stop()
        self.is_hovered_on_input = True
        self.is_hovered = True
        
        # 如果处于隐藏状态，恢复正常显示后再处理悬停逻辑
        if self.is_hidden:
            self.restore_from_edge()

    def on_input_hover_leave(self):
        self.leave_check_timer.start(50)

    def update_display_position(self):
        """更新显示框位置，当显示框高度改变时调用"""
        if not self.is_input_visible:
            return
            
        # 获取当前屏幕信息
        current_screen = self.get_current_screen()
        
        # 获取各组件尺寸
        ball_pos = self.pos()
        ball_width = self.width()
        ball_height = self.height()
        scaled_input_width = self.input_widget.width()
        scaled_input_height = self.input_widget.height()
        scaled_display_width = self.display_widget.width()
        scaled_display_height = self.display_widget.height()
        
        # 重新计算位置
        input_x = self.input_widget.x()
        input_y = self.input_widget.y()
        
        # 显示框底部 = 输入框顶部（无空隙）
        display_x = input_x
        display_y = input_y - scaled_display_height
        
        # 边界检查（确保在屏幕内）
        if display_y < current_screen.y():
            offset = current_screen.y() - display_y
            display_y += offset
            input_y += offset
        if input_y + scaled_input_height > current_screen.y() + current_screen.height():
            offset = (input_y + scaled_input_height) - (current_screen.y() + current_screen.height()) + 5
            input_y -= offset
            display_y -= offset
        
        # 更新位置
        self.input_widget.move(input_x, input_y)
        self.display_widget.move(display_x, display_y)
    
    def show_input_components(self):
        if not self.is_input_visible:
            # 获取悬浮球基础信息
            ball_pos = self.pos()
            ball_width = self.width()
            ball_height = self.height()
            current_screen = self.get_current_screen()
            self.last_screen_geometry = current_screen

            # 重新初始化输入框和显示框时传入保存的内容
            if hasattr(self, 'input_widget') and self.input_widget:
                self.input_widget.hide()
            if hasattr(self, 'display_widget') and self.display_widget:
                self.display_widget.hide()
            self.input_widget = ChatInputBox(self)
            self.display_widget = ChatDisplayBox(self, self.saved_display_content)
            
            # 应用保存的显示框高度
            if self.saved_display_height and self.saved_display_height >= self.display_widget.min_height:
                self.display_widget.resize(self.display_widget.width(), self.saved_display_height)
                self.display_widget.display_text_edit.setMinimumHeight(self.saved_display_height - 40)

            # 获取缩放后的尺寸
            scaled_input_width = self.input_widget.width()
            scaled_input_height = self.input_widget.height()
            scaled_display_width = self.display_widget.width()
            scaled_display_height = self.display_widget.height()

            # 计算输入框位置
            input_x = ball_pos.x() - scaled_input_width - 5
            input_y = ball_pos.y() + (ball_height - scaled_input_height) // 2
            if input_x < current_screen.x():
                input_x = ball_pos.x() + ball_width + 5

            # 显示框底部 = 输入框顶部（无空隙）
            display_x = input_x
            display_y = input_y - scaled_display_height

            # 边界检查（确保在屏幕内）
            if display_y < current_screen.y():
                offset = current_screen.y() - display_y
                display_y += offset
                input_y += offset
            if input_y + scaled_input_height > current_screen.y() + current_screen.height():
                offset = (input_y + scaled_input_height) - (current_screen.y() + current_screen.height()) + 5
                input_y -= offset
                display_y -= offset

            # 显示组件
            self.input_widget.move(input_x, input_y)
            self.display_widget.move(display_x, display_y)
            self.display_widget.show()
            self.input_widget.show()

            # 如果有截图，显示缩略图
            if self.screenshot_path and os.path.exists(self.screenshot_path):
                self.input_widget.show_screenshot_thumbnail(self.screenshot_path)

            self.is_input_visible = True
            self.is_display_visible = True

    def show_input(self):
        self.show_input_components()

    def animate_to_large(self):
        current_pos = self.pos()
        current_center_x = current_pos.x() + self.small_size // 2
        current_center_y = current_pos.y() + self.small_size // 2
        new_size = self.large_size
        new_x = current_center_x - new_size // 2
        new_y = current_center_y - new_size // 2
        self.animation.setStartValue(QRect(current_pos.x(), current_pos.y(), self.small_size, self.small_size))
        self.animation.setEndValue(QRect(new_x, new_y, new_size, new_size))
        self.animation.start()
        QTimer.singleShot(0, self.update_label_size_large)

    def animate_to_small(self):
        current_pos = self.pos()
        current_center_x = current_pos.x() + self.large_size // 2
        current_center_y = current_pos.y() + self.large_size // 2
        new_size = self.small_size
        new_x = current_center_x - new_size // 2
        new_y = current_center_y - new_size // 2
        self.animation.setStartValue(QRect(current_pos.x(), current_pos.y(), self.large_size, self.large_size))
        self.animation.setEndValue(QRect(new_x, new_y, new_size, new_size))
        if self.animation.state() == QPropertyAnimation.Running:
            self.animation.stop()
        self.animation.start()
        QTimer.singleShot(10, self.update_label_size_small)

    def update_label_size_large(self):
        self.resize(self.large_size, self.large_size)
        
        # Update mask for large size
        mask = QRegion(self.rect(), QRegion.Ellipse)
        self.setMask(mask)
        
        scaled_pixmap = self.original_pixmap.scaled(
            self.large_size, self.large_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.label.setPixmap(scaled_pixmap)
        self.label.setGeometry(0, 0, self.large_size, self.large_size)

    def update_label_size_small(self):
        self.resize(self.small_size, self.small_size)

        # Update mask for small size
        mask = QRegion(self.rect(), QRegion.Ellipse)
        self.setMask(mask)

        self.label.setPixmap(self.small_pixmap)
        self.label.setGeometry(0, 0, self.small_size, self.small_size)

    def move_to_corner(self):
        screen_geometry = self.get_current_screen()
        window_geometry = self.geometry()
        x = screen_geometry.width() - window_geometry.width() - 20
        y = screen_geometry.height() - (screen_geometry.height() // 3) - window_geometry.height() // 2
        self.move(x, y)

    def get_current_screen(self):
        desktop = QDesktopWidget()
        current_pos = self.pos()
        for i in range(desktop.screenCount()):
            screen_geometry = desktop.screenGeometry(i)
            if screen_geometry.contains(current_pos):
                return screen_geometry
        return desktop.screenGeometry()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 拖动时立即退出隐藏状态
            if self.is_hidden:
                self.restore_from_edge()
                
            self.dragging = True
            self.drag_position = event.globalPos() - self.pos()
            if self.animation.state() == QPropertyAnimation.Running:
                self.animation.stop()
                if self.is_hovered:
                    self.update_label_size_large()
                else:
                    self.update_label_size_small()
            self.trajectory_points = []
            self.current_screen = self.get_current_screen()
            self.trajectory_window.set_screen(self.current_screen)
            # 拖动前保存显示内容
            if self.display_widget:
                self.saved_display_content = self.display_widget.display_text
            # 隐藏并删除缩略图
            if self.input_widget:
                self.input_widget.hide_thumbnail()
                self.input_widget.hide()
                self.is_input_visible = False
            if self.display_widget:
                self.display_widget.hide()
                self.is_display_visible = False
            self.is_hovered_on_input = False
            self.is_hovered_on_display = False
            self.is_hovered = False
            self.is_waiting = False  # 拖动时重置等待状态
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPos() - self.drag_position)
            center = self.geometry().center()
            self.trajectory_points.append(center)
            if not self.trajectory_window.isVisible():
                self.trajectory_window.show()
            self.trajectory_window.update_trajectory(self.trajectory_points)
            current_screen = self.get_current_screen()
            if self.last_screen_geometry is None or self.last_screen_geometry != current_screen:
                self.trajectory_window.set_screen(current_screen)
                self.last_screen_geometry = current_screen
                if self.is_input_visible:
                    self.input_widget.hide()
                    self.is_input_visible = False
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.trajectory_window.hide()
            result = self.check_enclosed_area()
            self.trajectory_points = []
            
            # 如果悬浮球处于隐藏状态，先恢复显示
            if self.is_hidden:
                self.restore_from_edge()
                
            if self.is_hovered:
                current_screen = self.get_current_screen()
                if self.last_screen_geometry is None or self.last_screen_geometry != current_screen:
                    self.last_screen_geometry = current_screen
                    if self.input_widget:
                        self.input_widget.hide()
                    if self.display_widget:
                        self.display_widget.hide()
                    self.input_widget = ChatInputBox(self)
                    # 释放鼠标后重新创建显示框时传入保存的内容
                    self.display_widget = ChatDisplayBox(self, self.saved_display_content)
                QTimer.singleShot(100, self.show_input)
            else:
                # 检查是否需要隐藏到边缘
                self.check_and_hide_to_edge()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.move_to_corner()
        event.accept()

    def set_waiting_state(self, state):
        """设置等待状态"""
        self.is_waiting = state

    def on_thumbnail_deleted(self):
        """处理缩略图被删除的情况"""
        self.screenshot_path = None

    def check_enclosed_area(self):
        if len(self.trajectory_points) < 10:
            return None
        first_point = self.trajectory_points[0]
        last_point = self.trajectory_points[-1]
        distance = math.sqrt((first_point.x() - last_point.x()) **2 +
                             (first_point.y() - last_point.y())** 2)
        max_distance = 0
        farthest_points = (None, None)
        for i in range(len(self.trajectory_points)):
            for j in range(i + 1, len(self.trajectory_points)):
                p1 = self.trajectory_points[i]
                p2 = self.trajectory_points[j]
                dist = math.sqrt((p1.x() - p2.x()) **2 + (p1.y() - p2.y())** 2)
                if dist > max_distance:
                    max_distance = dist
                    farthest_points = (p1, p2)
        if distance < 50 and max_distance > 80:
            self.hide()
            min_x = min(p.x() for p in self.trajectory_points)
            min_y = min(p.y() for p in self.trajectory_points)
            max_x = max(p.x() for p in self.trajectory_points)
            max_y = max(p.y() for p in self.trajectory_points)
            top_left = QPoint(min_x, min_y)
            bottom_right = QPoint(max_x, max_y)
            print(f"检测到封闭图形:")
            print(
                f"距离最远的两个点坐标: ({farthest_points[0].x()}, {farthest_points[0].y()}) 和 ({farthest_points[1].x()}, {farthest_points[1].y()})")
            print(f"两点间距离: {max_distance:.2f}")
            print(f"最小外接矩形左上角: ({top_left.x()}, {top_left.y()})")
            print(f"最小外接矩形右下角: ({bottom_right.x()}, {bottom_right.y()})")
            # 保存截图路径
            self.screenshot_path = self.capture_and_save_rectangle(top_left, bottom_right)
            self.show()
            return {
                'point1': farthest_points[0],
                'point2': farthest_points[1],
                'distance': max_distance,
                'rect_top_left': top_left,
                'rect_bottom_right': bottom_right
            }
        return None

    def setup_context_menu(self):
        """设置右键菜单"""
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # 创建菜单
        self.context_menu = QMenu(self)
        
        # 创建菜单项
        self.enter_setting_action = QAction("进入设置页", self)
        self.exit_action = QAction("退出软件", self)
        
        # 连接信号与槽
        self.enter_setting_action.triggered.connect(self.enter_setting_page)
        self.exit_action.triggered.connect(self.exit_application)
        
        # 添加菜单项到菜单
        self.context_menu.addAction(self.enter_setting_action)
        self.context_menu.addAction(self.exit_action)
        
        # 设置菜单项样式
        self.context_menu.setStyleSheet("""
            QMenu {
                background-color: #333;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 24px;
                color: white;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QMenu::separator {
                background-color: #555;
                height: 1px;
                margin: 4px 0;
            }
        """)
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        self.context_menu.exec_(self.mapToGlobal(position))
    
    def enter_setting_page(self):
        """Launches the settings page (open_assistant_launcher.py)."""
        print("Attempting to open settings page...")
        try:
            # Get the directory where the current script is running
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Construct the full path to the launcher script
            launcher_script_path = os.path.join(current_dir, "open_assistant_launcher.py")
            
            if os.path.exists(launcher_script_path):
                print(f"Found launcher script at: {launcher_script_path}")
                # Use the same python interpreter that is running this script
                python_executable = sys.executable
                
                # Launch the settings window in a new process
                subprocess.Popen(
                    [python_executable, launcher_script_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                print("Settings page launch command issued.")
            else:
                print(f"Error: Launcher script not found at {launcher_script_path}")
        except Exception as e:
            print(f"An error occurred while trying to open the settings page: {str(e)}")
    

    
    def check_and_hide_to_edge(self):
        """检查是否需要隐藏到屏幕边缘"""
        if not self.is_hidden and not self.is_hovered:
            current_pos = self.pos()
            current_size = self.size()
            screen = self.get_current_screen()
            
            # 检查是否靠近左边缘
            if current_pos.x() <= screen.x() + self.edge_margin:
                self.hide_to_left_edge()
            # 检查是否靠近右边缘
            elif current_pos.x() + current_size.width() >= screen.x() + screen.width() - self.edge_margin:
                self.hide_to_right_edge()
    
    def hide_to_left_edge(self):
        """隐藏到左侧边缘 - 显示蓝色条时悬浮球完全隐藏"""
        self.is_hidden = True
        current_pos = self.pos()
        screen = self.get_current_screen()
        
        # 隐藏主标签（悬浮球）
        self.label.hide()
        
        # 显示边缘标签（蓝色条）
        self.edge_label.setGeometry(0, 0, self.hidden_width, self.height())
        self.edge_label.show()
        self.edge_label.raise_()  # 确保蓝色条在最上层
        
        # 移动窗口到左侧边缘，确保蓝色条完全可见
        new_x = screen.x()
        self.move(new_x, current_pos.y())
    
    def hide_to_right_edge(self):
        """隐藏到右侧边缘 - 显示蓝色条时悬浮球完全隐藏"""
        self.is_hidden = True
        current_pos = self.pos()
        screen = self.get_current_screen()
        
        # 隐藏主标签（悬浮球）
        self.label.hide()
        
        # 显示边缘标签（蓝色条）
        self.edge_label.setGeometry(self.width() - self.hidden_width, 0, self.hidden_width, self.height())
        self.edge_label.show()
        self.edge_label.raise_()  # 确保蓝色条在最上层
        
        # 移动窗口到右侧边缘，确保蓝色条完全可见
        new_x = screen.x() + screen.width() - self.width()
        self.move(new_x, current_pos.y())
    
    def restore_from_edge(self):
        """从边缘恢复显示 - 显示悬浮球时蓝色条完全隐藏"""
        self.is_hidden = False
        current_pos = self.pos()
        screen = self.get_current_screen()
        
        # 隐藏边缘标签（蓝色条），显示主标签（悬浮球）
        self.edge_label.hide()
        self.label.show()
        
        # 确保窗口完全在屏幕内且位置合适
        if current_pos.x() <= screen.x() + 10:
            new_x = screen.x() + 10  # 稍微离开边缘一点
            self.move(new_x, current_pos.y())
        elif current_pos.x() + self.width() >= screen.x() + screen.width() - 10:
            new_x = screen.x() + screen.width() - self.width() - 10  # 稍微离开边缘一点
            self.move(new_x, current_pos.y())
    
    def resizeEvent(self, event):
        """Override resize event to maintain a circular mask."""
        super().resizeEvent(event)
        self.setMask(QRegion(self.rect(), QRegion.Ellipse))

    def exit_application(self):
        """关闭mcp_agent.exe进程"""
        print("正在关闭mcp_agent.exe进程...")
        
        # 首先确保data目录存在
        import os
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir)
                print(f"已创建data目录: {data_dir}")
            except Exception as e:
                print(f"创建data目录时出错: {e}")
        
        # 创建退出标志文件
        exit_flag_file = os.path.join(data_dir, "exit_flag.txt")
        try:
            with open(exit_flag_file, "w") as f:
                f.write("exit")
            print(f"已创建退出标志文件: {exit_flag_file}")
        except Exception as e:
            print(f"创建退出标志文件时出错: {e}")
        
        # 使用QTimer来确保应用程序能够立即响应，避免阻塞
        from PyQt5.QtCore import QTimer
        
        def close_mcp_process():
            # 关闭mcp_agent.exe进程
            try:
                import psutil
                mcp_process_found = False
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'] == 'mcp_agent.exe':
                            mcp_process_found = True
                            print(f"找到mcp_agent.exe进程，PID: {proc.info['pid']}")
                            proc.terminate()
                            # 等待进程终止，最多等待5秒
                            try:
                                proc.wait(timeout=5)
                                print(f"已成功终止mcp_agent.exe进程，PID: {proc.info['pid']}")
                            except psutil.TimeoutExpired:
                                print(f"终止mcp_agent.exe进程超时，强制终止")
                                proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                if not mcp_process_found:
                    print("未找到mcp_agent.exe进程")
                
            except ImportError:
                print("未安装psutil库，无法关闭mcp_agent.exe进程")
            except Exception as e:
                print(f"关闭mcp_agent.exe进程时出错: {e}")
        
        # 使用单次定时器在100毫秒后执行关闭进程操作
        QTimer.singleShot(100, close_mcp_process)
    
    def capture_and_save_rectangle(self, top_left, bottom_right):
        desktop = QDesktopWidget()
        screen_number = desktop.screenNumber(top_left)
        screen = QApplication.screens()[screen_number] if QApplication.screens() else QGuiApplication.primaryScreen()
        
        # 获取屏幕的缩放因子（devicePixelRatio）
        # 这对于高DPI屏幕（如2K）非常重要，可以确保逻辑坐标正确映射到物理像素
        scale_factor = screen.devicePixelRatio()
        print(f"屏幕缩放因子: {scale_factor}")
        
        # 使用logicalDotsPerInch获取另一个缩放参考值
        logical_dpi = screen.logicalDotsPerInch()
        dpi_scale = logical_dpi / 96.0
        print(f"DPI缩放因子: {dpi_scale}")
        
        # 获取屏幕几何体
        screen_geometry = screen.geometry()
        
        # 计算实际的截图区域坐标，考虑缩放因子
        # 对于Qt中的高DPI屏幕，top_left和bottom_right是逻辑坐标
        # 我们需要将它们转换为物理坐标来正确截图
        x1_local = int((top_left.x() - screen_geometry.x()) * scale_factor)
        y1_local = int((top_left.y() - screen_geometry.y()) * scale_factor)
        x2_local = int((bottom_right.x() - screen_geometry.x()) * scale_factor)
        y2_local = int((bottom_right.y() - screen_geometry.y()) * scale_factor)
        
        # 使用grabWindow获取屏幕截图（注意这会返回物理像素的图像）
        screenshot = screen.grabWindow(0)
        qimg = screenshot.toImage()
        temp_buffer = qimg.bits().asstring(qimg.byteCount())
        img = np.frombuffer(temp_buffer, dtype=np.uint8)
        img = img.reshape((qimg.height(), qimg.width(), 4))
        
        print(f"逻辑坐标范围: ({top_left.x()}, {top_left.y()}) 到 ({bottom_right.x()}, {bottom_right.y()})")
        print(f"物理坐标范围: ({x1_local}, {y1_local}) 到 ({x2_local}, {y2_local})")
        print(f"图像尺寸: {img.shape[1]}x{img.shape[0]}")
        x1_local = max(0, min(x1_local, img.shape[1]))
        x2_local = max(0, min(x2_local, img.shape[1]))
        y1_local = max(0, min(y1_local, img.shape[0]))
        y2_local = max(0, min(y2_local, img.shape[0]))

        # 生成唯一的图片文件名
        timestamp = int(time.time())
        image_path = f"imgs/test2.png"

        if x1_local < x2_local and y1_local < y2_local:
            cropped_img = img[y1_local:y2_local, x1_local:x2_local]
            if not os.path.exists("imgs"):
                os.makedirs("imgs")
            cv2.imwrite(image_path, cropped_img)
            print(f"截图已保存到: {image_path}")

            # 如果输入框可见，立即显示缩略图
            if self.is_input_visible and self.input_widget:
                self.input_widget.show_screenshot_thumbnail(image_path)

            return image_path
        return None


def launch_assistant_avatar():
    app = QApplication(sys.argv)
    # 高DPI设置已在导入后创建QApplication前设置，这里不再需要
    
    # 清空JSON文件
    try:
        # 确保数据目录存在
        if not os.path.exists("data"):
            os.makedirs("data")
        # 清空输入文件
        with open(INPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        # 清空输出文件
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        print("JSON文件已清空")
    except Exception as e:
        print(f"清空JSON文件时出错: {e}")

    font = app.font()
    font.setPointSize(9)
    app.setFont(font)
    # 启动通信管理器
    comm_manager.start()
    floating_ball = AssistantAvatar()
    try:
        sys.exit(app.exec_())
    finally:
        # 清理资源
        comm_manager.stop()


if __name__ == "__main__":
    launch_assistant_avatar()
    