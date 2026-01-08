# services/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

class AppLogger:
    """統一日誌管理系統"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str = "rental_app") -> logging.Logger:
        """取得或建立 logger 實例"""
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'INFO')))
        
        # 避免重複添加 handler
        if logger.handlers:
            return logger
        
        # 格式化
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s [%(name)s:%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File Handler（自動輪轉，最多保留 5 個檔案，每個 10MB）
        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger

# 建立全域 logger
logger = AppLogger.get_logger()

# 使用範例函數
def log_db_operation(operation: str, table: str, success: bool, 
                     row_count: int = None, error: str = None):
    """記錄資料庫操作"""
    if success:
        msg = f"DB操作成功: {operation} on {table}"
        if row_count is not None:
            msg += f" ({row_count} rows)"
        logger.info(msg)
    else:
        logger.error(f"DB操作失敗: {operation} on {table} - {error}")

def log_user_action(action: str, details: dict):
    """記錄使用者操作"""
    logger.info(f"用戶操作: {action}", extra=details)
