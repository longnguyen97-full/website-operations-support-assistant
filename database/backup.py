import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

from config import DATA_DIR, DB_PATH, TZ_VN
from database.db import get_db_connection, init_db

BACKUPS_DIR = DATA_DIR / "backups"

def ensure_backup_dir() -> Path:
    """Tạo thư mục data/backups nếu chưa tồn tại."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUPS_DIR

def create_db_backup(custom_name: Optional[str] = None) -> Tuple[bool, str, Optional[Path]]:
    """
    Tạo bản sao lưu chuẩn ACID của SQLite bằng phương thức Online Backup API.
    Đảm bảo an toàn không bị khóa file hay lỗi dữ liệu ngay cả khi hệ thống đang ghi logs.
    """
    ensure_backup_dir()
    if not DB_PATH.exists():
        init_db()

    ts_str = datetime.now(TZ_VN).strftime("%Y%m%d_%H%M%S")
    if custom_name:
        safe_custom = "".join(c for c in custom_name if c.isalnum() or c in ("-", "_")).strip()
        backup_filename = f"monitoring_backup_{ts_str}_{safe_custom}.db"
    else:
        backup_filename = f"monitoring_backup_{ts_str}.db"

    target_path = BACKUPS_DIR / backup_filename

    source_conn = None
    dest_conn = None
    try:
        source_conn = get_db_connection()
        dest_conn = sqlite3.connect(str(target_path))
        
        # Sử dụng API Online Backup của SQLite
        source_conn.backup(dest_conn)
        
        dest_conn.close()
        source_conn.close()
        return True, f"Đã tạo bản sao lưu thành công: {backup_filename}", target_path
    except Exception as e:
        if dest_conn:
            try:
                dest_conn.close()
            except Exception:
                pass
        if source_conn:
            try:
                source_conn.close()
            except Exception:
                pass
        return False, f"Lỗi khi sao lưu cơ sở dữ liệu: {e}", None

def get_all_db_backups() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các bản sao lưu cục bộ trong data/backups/."""
    ensure_backup_dir()
    backups = []
    
    for f in sorted(BACKUPS_DIR.glob("*.db"), key=os.path.getmtime, reverse=True):
        stat = f.stat()
        created_time = datetime.fromtimestamp(stat.st_mtime, tz=TZ_VN).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = round(stat.st_size / 1024, 2)
        
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_kb": size_kb,
            "created_time": created_time,
            "is_safety": "safety" in f.name.lower()
        })
    return backups

def get_current_db_bytes() -> Optional[bytes]:
    """Đọc dữ liệu nhị phân của file database hiện tại để phục vụ download."""
    if not DB_PATH.exists():
        init_db()
    
    # Tạo một bản snapshot tạm thời để đọc dữ liệu nhất quán
    source_conn = None
    temp_path = DATA_DIR / "_temp_export.db"
    try:
        source_conn = get_db_connection()
        dest_conn = sqlite3.connect(str(temp_path))
        source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()
        
        with open(temp_path, "rb") as f:
            data = f.read()
        
        temp_path.unlink(missing_ok=True)
        return data
    except Exception as e:
        if source_conn:
            try:
                source_conn.close()
            except Exception:
                pass
        temp_path.unlink(missing_ok=True)
        
        # Fallback đọc trực tiếp file nếu có
        try:
            with open(DB_PATH, "rb") as f:
                return f.read()
        except Exception:
            return None

def inspect_sqlite_bytes(file_bytes: bytes) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Kiểm tra tính hợp lệ và cấu trúc schema của file SQLite trước khi khôi phục.
    """
    if not file_bytes.startswith(b"SQLite format 3\x00"):
        return False, "File tải lên không phải là cơ sở dữ liệu SQLite hợp lệ!", {}

    temp_path = DATA_DIR / "_temp_inspect.db"
    try:
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        conn = sqlite3.connect(str(temp_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Kiểm tra danh sách bảng
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]

        # Kiểm tra bảng cốt lõi
        if "websites" not in tables:
            conn.close()
            temp_path.unlink(missing_ok=True)
            return False, "File CSDL thiếu bảng 'websites' cốt lõi của hệ thống.", {}

        # Thống kê nhanh dữ liệu bên trong file
        cursor.execute("SELECT COUNT(*) FROM websites;")
        site_count = cursor.fetchone()[0]

        log_count = 0
        if "monitoring_logs" in tables:
            cursor.execute("SELECT COUNT(*) FROM monitoring_logs;")
            log_count = cursor.fetchone()[0]

        baseline_count = 0
        if "milestone_baselines" in tables:
            cursor.execute("SELECT COUNT(*) FROM milestone_baselines;")
            baseline_count = cursor.fetchone()[0]

        conn.close()
        temp_path.unlink(missing_ok=True)

        return True, "CSDL hợp lệ và tương thích hoàn toàn!", {
            "tables": tables,
            "website_count": site_count,
            "log_count": log_count,
            "baseline_count": baseline_count,
            "size_kb": round(len(file_bytes) / 1024, 2)
        }
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        return False, f"Lỗi khi đọc cấu trúc CSDL: {e}", {}

def restore_db_from_bytes(file_bytes: bytes) -> Tuple[bool, str]:
    """
    Khôi phục cơ sở dữ liệu từ luồng bytes:
    1. Kiểm tra tính hợp lệ của file.
    2. Tự động tạo bản sao lưu an toàn (Safety Auto-Backup) của DB hiện tại.
    3. Ghi đè file DB_PATH.
    4. Chạy init_db() để đảm bảo cấu trúc và chỉ mục.
    """
    is_valid, msg, _ = inspect_sqlite_bytes(file_bytes)
    if not is_valid:
        return False, msg

    # 1. Tạo bản sao lưu an toàn của CSDL hiện tại
    if DB_PATH.exists():
        create_db_backup(custom_name="safety_before_restore")

    # 2. Ghi file mới
    temp_restore = DATA_DIR / "_temp_restore.db"
    try:
        with open(temp_restore, "wb") as f:
            f.write(file_bytes)

        # Ghi đè an toàn vào DB_PATH
        shutil.copy2(temp_restore, DB_PATH)
        temp_restore.unlink(missing_ok=True)

        # 3. Đồng bộ lại DB schema
        init_db()
        return True, "Khôi phục cơ sở dữ liệu thành công! Dữ liệu đã được nạp lại hoàn tất."
    except Exception as e:
        temp_restore.unlink(missing_ok=True)
        return False, f"Lỗi trong quá trình ghi đè CSDL: {e}"

def restore_db_from_file(backup_path: str) -> Tuple[bool, str]:
    """Khôi phục CSDL từ một file backup cục bộ có sẵn."""
    p = Path(backup_path)
    if not p.exists():
        return False, f"File sao lưu '{p.name}' không tồn tại!"

    try:
        with open(p, "rb") as f:
            content = f.read()
        return restore_db_from_bytes(content)
    except Exception as e:
        return False, f"Lỗi khi đọc file sao lưu: {e}"

def delete_db_backup(backup_path: str) -> Tuple[bool, str]:
    """Xóa một bản sao lưu cục bộ."""
    p = Path(backup_path)
    try:
        if p.exists() and p.parent.resolve() == BACKUPS_DIR.resolve():
            p.unlink()
            return True, f"Đã xóa bản sao lưu '{p.name}' thành công."
        return False, "File không tồn tại hoặc đường dẫn không hợp lệ."
    except Exception as e:
        return False, f"Lỗi khi xóa file: {e}"
