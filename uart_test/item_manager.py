import json
import os
import sys

class ItemManager:
    def __init__(self, json_file='uart_command_set.json', language='EN'):
        self.json_file = json_file
        self.language = language
        self.items = []
        self.organized_items = {}
        self.load_items()

    def get_resource_path(self, filename):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)
        return os.path.join(base_path, filename)

    def load_items(self):
        try:
            # 解析配置文件路径：支持绝对路径、相对调用cwd、以及模块相对路径
            json_path = self.json_file
            if not os.path.isabs(json_path):
                # 先尝试当前工作目录
                cwd_path = os.path.abspath(json_path)
                if os.path.exists(cwd_path):
                    json_path = cwd_path
                else:
                    # 回退到模块目录
                    json_path = self.get_resource_path(self.json_file)
            
            if not os.path.exists(json_path):
                raise FileNotFoundError(f"找不到配置文件: {json_path}")
                
            with open(json_path, 'r', encoding='utf-8') as f:
                self.items = json.load(f)
        except Exception as e:
            print(f"Error loading JSON file: {e}")
            # 显示更详细的错误信息
            import traceback
            traceback.print_exc()
            self.items = []
        self.organize_items()

    def organize_items(self):
        self.organized_items = {}
        for item in self.items:
            module = item.get("Module" if self.language == "EN" else "模块", "Uncategorized")
            submodule = item.get("Submodule" if self.language == "EN" else "子模块", "Others")
            if module not in self.organized_items:
                self.organized_items[module] = {}
            if submodule not in self.organized_items[module]:
                self.organized_items[module][submodule] = []
            self.organized_items[module][submodule].append(item)

    def set_language(self, lang):
        self.language = lang
        self.organize_items()

    def get_organized_items(self):
        return self.organized_items 