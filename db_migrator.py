"""
數據庫遷移工具 - v4.1
✅ 自動檢測需要遷移的檔案
✅ 生成遷移報告
✅ 提供遷移建議
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple


class DBMigrator:
    """數據庫遷移工具"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.views_dir = self.project_root / "views"
        self.repository_dir = self.project_root / "repository"

        # 需要遷移的模式（修正 regex：使用 \s 而不是 \\s）
        self.old_patterns: List[Tuple[str, str]] = [
            (
                r"from\s+services\.db\s+import\s+get_database_instance",
                "db import",
            ),
            (
                r"from\s+services\.db\s+import\s+SupabaseDB",
                "SupabaseDB import",
            ),
            (
                r"db\s*=\s*get_database_instance\(",
                "db instance",
            ),
            (
                r"db\.get_tenants\(",
                "tenant method",
            ),
            (
                r"db\.add_payment_schedule\(",
                "payment method",
            ),
            (
                r"db\.trigger_auto_first_notification\(",
                "notification method",
            ),
        ]

        # 新服務映射
        self.service_mapping: Dict[str, str] = {
            "get_tenants": "TenantService",
            "add_tenant": "TenantService",
            "update_tenant": "TenantService",
            "delete_tenant": "TenantService",
            "get_payment_schedule": "PaymentService",
            "add_payment_schedule": "PaymentService",
            "mark_payment_done": "PaymentService",
            "get_overdue_payments": "PaymentService",
            "add_electricity_period": "ElectricityService",
            "save_electricity_record": "ElectricityService",
            "trigger_auto_first_notification": "NotificationService",
            "add_expense": "ExpenseService",
            "add_memo": "MemoService",
        }

    # ==================== 掃描需要遷移的檔案 ====================

    def scan_files(self) -> List[Dict]:
        """掃描需要遷移的檔案"""
        migration_files: List[Dict] = []

        # 掃描 views/ 目錄
        if self.views_dir.exists():
            for py_file in self.views_dir.glob("*.py"):
                matches = self._check_file(py_file)
                if matches:
                    migration_files.append(
                        {
                            "file": str(py_file.relative_to(self.project_root)),
                            "matches": matches,
                            "priority": "high"
                            if any(
                                "trigger_auto_first_notification" in m[1]
                                for m in matches
                            )
                            else "medium",
                        }
                    )

        # 掃描 repository/ 目錄
        if self.repository_dir.exists():
            for py_file in self.repository_dir.glob("*.py"):
                matches = self._check_file(py_file)
                if matches:
                    migration_files.append(
                        {
                            "file": str(py_file.relative_to(self.project_root)),
                            "matches": matches,
                            "priority": "low",
                        }
                    )

        return migration_files

    def _check_file(self, file_path: Path) -> List[Tuple[str, str]]:
        """檢查檔案是否需要遷移"""
        matches: List[Tuple[str, str]] = []

        try:
            content = file_path.read_text(encoding="utf-8")

            for pattern, desc in self.old_patterns:
                if re.search(pattern, content):
                    matches.append((desc, pattern))

        except Exception as e:
            print(f"⚠️ 讀取檔案失敗: {file_path} - {e}")

        return matches

    # ==================== 遷移報告 ====================

    def generate_migration_report(self) -> str:
        """生成遷移報告"""
        migration_files = self.scan_files()

        if not migration_files:
            return """
╔══════════════════════════════════════════════════════════════════╗
║              ✅ 恭喜！無需遷移的檔案                             ║
╚══════════════════════════════════════════════════════════════════╝

所有檔案都已使用新的模組化服務，或者未檢測到舊的 db.py 調用。
"""

        report = f"""
╔══════════════════════════════════════════════════════════════════╗
║              📊 數據庫遷移報告 - v4.1                            ║
╚══════════════════════════════════════════════════════════════════╝

檢測到 {len(migration_files)} 個檔案需要遷移：

"""

        # 按優先級排序
        high_priority = [f for f in migration_files if f["priority"] == "high"]
        medium_priority = [f for f in migration_files if f["priority"] == "medium"]
        low_priority = [f for f in migration_files if f["priority"] == "low"]

        if high_priority:
            report += "🔴 高優先級（包含新功能）\n" + "=" * 70 + "\n"
            for file_info in high_priority:
                report += f"\n📄 {file_info['file']}\n"
                for desc, _ in file_info["matches"]:
                    report += f"   - {desc}\n"

        if medium_priority:
            report += "\n🟡 中優先級（views/ 目錄）\n" + "=" * 70 + "\n"
            for file_info in medium_priority:
                report += f"\n📄 {file_info['file']}\n"
                for desc, _ in file_info["matches"]:
                    report += f"   - {desc}\n"

        if low_priority:
            report += "\n🟢 低優先級（repository/ 目錄）\n" + "=" * 70 + "\n"
            for file_info in low_priority:
                report += f"\n📄 {file_info['file']}\n"
                for desc, _ in file_info["matches"]:
                    report += f"   - {desc}\n"

        report += """

╔══════════════════════════════════════════════════════════════════╗
║              🎯 遷移建議                                         ║
╚══════════════════════════════════════════════════════════════════╝

方案 A - 快速遷移（推薦）
─────────────────────────────────────────
只需將所有檔案中的：
  from services.db import get_database_instance
改為：
  from services.db_legacy import get_database_instance

✅ 優點：5 分鐘完成，舊程式碼繼續運作
✅ 新功能（電費通知寫入 notification_logs）立即可用


方案 B - 完整遷移（最佳實踐）
─────────────────────────────────────────
逐個檔案替換為新服務：

舊程式碼:
  from services.db import get_database_instance
  db = get_database_instance()
  db.get_tenants()

新程式碼:
  from services.tenant_service import TenantService
  tenant_svc = TenantService()
  tenant_svc.get_tenants()

✅ 優點：程式碼更清晰、易維護
⏰ 時間：每個檔案約 10-15 分鐘


╔══════════════════════════════════════════════════════════════════╗
║              📝 下一步行動                                       ║
╚══════════════════════════════════════════════════════════════════╝

1. 立即執行（本週）
   ├─ 複製所有 service 檔案到專案
   ├─ 將 db import 改為 db_legacy import
   └─ 測試電費通知是否寫入 notification_logs

2. 逐步遷移（下週）
   ├─ 從高優先級檔案開始
   ├─ 每天遷移 2-3 個檔案
   └─ 測試確保功能正常

3. 完成清理（兩週後）
   ├─ 刪除 services/db.py（舊檔案）
   ├─ 刪除 services/db_legacy.py（兼容層）
   └─ 所有檔案使用新服務

"""
        return report

    # ==================== 單檔建議 ====================

    def suggest_migration(self, file_path: str) -> str:
        """為特定檔案生成遷移建議"""
        file = Path(file_path)

        if not file.exists():
            return f"❌ 檔案不存在: {file}"

        try:
            content = file.read_text(encoding="utf-8")

            # 檢測使用的方法
            used_methods: List[Tuple[str, str]] = []
            for method, service in self.service_mapping.items():
                if f"db.{method}(" in content:
                    used_methods.append((method, service))

            if not used_methods:
                return f"✅ {file.name} 無需遷移"

            suggestion = f"""
╔══════════════════════════════════════════════════════════════════╗
║      📝 遷移建議: {file.name}
╚══════════════════════════════════════════════════════════════════╝

檢測到使用的方法：
"""
            for method, service in used_methods:
                suggestion += f"  - db.{method}() → {service}\n"

            # 生成新程式碼
            services_needed = list({s for _, s in used_methods})

            suggestion += """

建議的新程式碼：
─────────────────────────────────────────

# 1. 在檔案開頭新增 imports
"""
            for service in services_needed:
                module = service.lower().replace("service", "_service")
                suggestion += f"from services.{module} import {service}\n"

            suggestion += """

# 2. 在初始化處建立服務實例
"""
            for service in services_needed:
                var_name = service.lower().replace("service", "_svc")
                suggestion += f"{var_name} = {service}()\n"

            suggestion += """

# 3. 替換方法調用
"""
            for method, service in used_methods:
                var_name = service.lower().replace("service", "_svc")
                suggestion += f"db.{method}(...) → {var_name}.{method}(...)\n"

            return suggestion

        except Exception as e:
            return f"❌ 處理檔案失敗: {e}"


# ============================================================================


def main():
    """命令列工具主程式"""
    migrator = DBMigrator()

    if len(sys.argv) > 1:
        # 為特定檔案生成建議
        file_path = sys.argv[1]
        print(migrator.suggest_migration(file_path))
    else:
        # 生成完整報告
        print(migrator.generate_migration_report())


if __name__ == "__main__":
    main()
