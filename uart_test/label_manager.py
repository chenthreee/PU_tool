import json
import os
import sys

def get_resource_path(filename):
    """
    获取资源文件路径，兼容开发环境和PyInstaller打包后的环境
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的exe
        base_path = sys._MEIPASS
    else:
        # 源码运行：使用模块所在目录
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, filename)

class LabelManager:
    def __init__(self):
        self.current_language = "CN"
        self.labels = {}
        self.load_labels()

    def load_labels(self):
        try:
            label_file = get_resource_path('label.json')
            print(f"Attempting to load label file: {label_file}")
            print(f"File exists: {os.path.exists(label_file)}")
            
            with open(label_file, 'r', encoding='utf-8') as f:
                self.labels = json.load(f)
                print("Successfully loaded label file")
        except Exception as e:
            print(f"Error loading labels: {e}")
            self.labels = {}

    def get_label(self, key):
        if key in self.labels:
            return self.labels[key].get(self.current_language, key)
        return key

    def set_language(self, lang):
        self.current_language = lang 