# services/logger.py
"""
統一日誌系統
用於記錄應用程式運行狀態、錯誤、業務操作
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

class AppLogger:
    """應用程式日誌管理器"""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """初始化 logger 配置"""
        # 建立 logs 目錄
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 取得日誌等級（從環境變數或預設 INFO）
        log_level_str = os.getenv('LOG_LEVEL', 'INFO')
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        
        # 建立 logger
        self._logger = logging.getLogger('rental_app')
        self._logger.setLevel(log_level)
        
        # 避免重複添加 handler
        if self._logger.handlers:
            return
        
        # 格式化器
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s [%(name)s:%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console Handler（輸出到終端）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        # File Handler（輸出到檔案，自動輪轉）
        try:
            file_handler = RotatingFileHandler(
                log_dir / 'app.log',
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        except Exception as e:
            print(f"⚠️ 無法建立檔案日誌 handler: {e}")
    
    @property
    def logger(self):
        """取得 logger 實例"""
        return self._logger


# 建立全域 logger 實例（方便其他模組 import）
logger = AppLogger().logger


# 使用範例
if __name__ == "__main__":
    logger.debug("這是 DEBUG 訊息")
    logger.info("這是 INFO 訊息")
    logger.warning("這是 WARNING 訊息")
    logger.error("這是 ERROR 訊息")
    logger.critical("這是 CRITICAL 訊息")
