"""
CSV历史数据记录模块
每个Model一个CSV文件，追加写入，不重写整个文件，不会因数据量变大而卡顿
"""

import os
import csv
import time
import threading
import queue
from datetime import datetime
from typing import Dict, Any, Optional


class CsvHistoryRecorder:
    """CSV历史数据记录器，每个Model对应一个CSV文件"""

    def __init__(self, save_dir: str = None):
        self.save_dir = save_dir        # 保存目录，None时enable()自动生成
        self.enabled = False

        self._write_queue = queue.Queue(maxsize=500)
        self._writer_thread = None
        self._stop_event = threading.Event()

        # 每个model_id对应的一个已经打开了的文件句柄还有csv.writer
        # model_id 里面： file：f writer：w header：就是每个表格中对应的所有项目 
        #path 就是路劲 就是遗传string
        # { model_id: {"file": f, "writer": w, "headers": [...], "path": str} }
        self._file_cache: Dict[int, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def enable(self, save_dir: str = None):
        """启用记录。可传入目录路径，不传则自动生成带时间戳的目录"""
        if save_dir:
            self.save_dir = save_dir

        if not self.save_dir:
            #时间戳 如果是重新关掉打开的exe运行 那就会直接新建一个文件
            #否则 就是在原csv上追加 追加的第一列就会写下这个时间戳
            #不过因为是csv文件 每次timestamp时间戳重新设置了单元格式 依旧无法保存
            #改成使用excel的话 同时打开多个openpyxl文件的会有卡顿的问题

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            try:
                #可以考虑是 当前路劲还是 用户目录~/Documents
                #C:\Users\Administrator\Documents 
                base = os.path.expanduser("./Documents")
                #如果不存在的话就是直接获取的当前目录存放这些文件即可
                if not os.path.exists(base):
                    base = os.getcwd()
            except Exception:
                base = os.getcwd()
            self.save_dir = os.path.join(base, f"SunSpec_Log_{timestamp}")

        os.makedirs(self.save_dir, exist_ok=True)
        self.enabled = True
        self._stop_event.clear()

        if not self._writer_thread or not self._writer_thread.is_alive():
            self._writer_thread = threading.Thread(
                target=self._worker, daemon=True, name="CsvRecorderWorker"
            )
            self._writer_thread.start()
        #有正常打印 
        print(f"[CsvRecorder] enabled, save_dir={self.save_dir}")
        return self.save_dir

    def disable(self):
        """停止接收新数据，等待写线程把队列里剩余数据写完后退出"""
        self.enabled = False
        self._stop_event.set()
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=5.0)
        self._close_all_files()
        #整个界面关闭后 有正常打印这句 [CsvRecorder] disable
        print("[CsvRecorder] disabled")

    def record_model_data(self, model_id: int, parsed_data: Dict[str, Any],
                          timestamp: float = None):
        """记录一条模型数据（在解析线程调用，非阻塞）"""
        if not self.enabled:
            return
        if timestamp is None:
            timestamp = time.time()
        try:
            self._write_queue.put_nowait((model_id, parsed_data, timestamp))
        except queue.Full:
            pass  # 队列满则丢弃，不阻塞调用方

    def close(self):
        """程序退出时调用"""
        self.disable()

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _worker(self):
        """写线程：持续从队列取数据写入对应CSV"""
        while True:
            # 队列空且收到停止信号，退出 
            if self._stop_event.is_set() and self._write_queue.empty():
                break
            try:
                item = self._write_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            model_id, parsed_data, timestamp = item
            try:
                self._write_row(model_id, parsed_data, timestamp)
            except Exception as e:
                print(f"[CsvRecorder] write error model {model_id}: {e}")

    def _write_row(self, model_id: int, parsed_data: Dict[str, Any], timestamp: float):
        """将一行数据写入对应model的CSV文件"""
        with self._lock:
            file_info = self._get_or_create_file(model_id, parsed_data)
            if file_info is None:
                return

            writer = file_info["writer"]
            headers = file_info["headers"]

            # 构造行：第一列时间戳 格式 eg：2026-04-10 15:29:33
            dt_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            row = [dt_str]

            # 按表头顺序填值（用label匹配）
            for label in headers[1:]:
                value = ""
                for field_name, field_data in parsed_data.items():
                    if not isinstance(field_data, dict):
                        continue
                    if field_data.get("label", field_name) == label:
                        value = self._extract_value(field_data)
                        break
                row.append(value)

            writer.writerow(row)
            file_info["file"].flush()  # 每行立即刷盘，崩溃也不丢数据

    def _get_or_create_file(self, model_id: int, parsed_data: Dict[str, Any]) -> Optional[dict]:
        """获取或创建model对应的CSV文件，返回file_info字典"""
        if model_id in self._file_cache:
            return self._file_cache[model_id]

        # 生成文件路径
        filename = f"Model_{model_id}.csv"
        filepath = os.path.join(self.save_dir, filename)

        # 构建表头：Timestamp + 各字段label（按parsed_data顺序）
        headers = ["Timestamp"]
        for field_name, field_data in parsed_data.items():
            if isinstance(field_data, dict):
                label = field_data.get("label", field_name)
            else:
                label = field_name
            headers.append(label)

        # 判断文件是否已存在（续写 or 新建）
        file_exists = os.path.exists(filepath)

        try:
            f = open(filepath, "a", newline="", encoding="utf-8")
            writer = csv.writer(f)

            if not file_exists or os.path.getsize(filepath) == 0:
                # 新文件，写表头
                writer.writerow(headers)
                f.flush()

            #此处是凭借file info 到时候可以批量一整个数据结构
            file_info = {
                "file": f,
                "writer": writer,
                "headers": headers,
                "path": filepath,
            }
            self._file_cache[model_id] = file_info
            #这一句在终端terminal中是一直有打印的
            print(f"[CsvRecorder] opened {filepath}")
            return file_info

        except Exception as e:
            print(f"[CsvRecorder] failed to open {filepath}: {e}")
            return None

    def _extract_value(self, field_data: dict) -> str:
        """从字段数据提取原始值，数组转逗号分隔字符串"""
        # 优先取 raw / raw_value，再取 value
        if "raw" in field_data:
            val = field_data["raw"]
        elif "raw_value" in field_data:
            val = field_data["raw_value"]
        else:
            val = field_data.get("value")
        
        if isinstance(val, (list, tuple)):
            try:
                return ",".join(str(int(x)) for x in val)
            except Exception:
                return ",".join(str(x) for x in val)

        if val is None:
            return ""
        return str(val)

    def _close_all_files(self):
        """关闭所有已打开的CSV文件"""
        with self._lock:
            for model_id, info in self._file_cache.items():
                try:
                    info["file"].close()
                except Exception:
                    pass
            self._file_cache.clear()
