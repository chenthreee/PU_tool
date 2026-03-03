import datetime

class LogManager:
    def __init__(self):
        self.log_file_path = None
        self.log_callback = None  # 用于GUI回调显示

    def set_log_callback(self, callback):
        self.log_callback = callback

    def set_log_file_path(self, path):
        self.log_file_path = path

    def add_log(self, message):
        now = datetime.datetime.now()
        #timestamp = now.strftime("[%Y-%m-%d %H:%M:%S.%f]")[:-3]
        timestamp = now.strftime("%H:%M:%S")
        msg = f"{timestamp} {message}"
        if self.log_callback:
            self.log_callback(msg)
        if self.log_file_path:
            try:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(msg + '\n')
            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"Failed to write log file: {e}")

    def clear_log(self):
        if self.log_callback:
            self.log_callback("__CLEAR__")

    def save_current_log_to_file(self, log_content):
        if self.log_file_path:
            try:
                with open(self.log_file_path, "w", encoding="utf-8") as f:
                    f.write(log_content)
            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"Failed to save log: {e}") 