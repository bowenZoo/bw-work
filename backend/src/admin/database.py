"""
SQLite database management for Admin module.
"""

import os
import secrets
import sqlite3
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class AdminDatabase:
    """Admin database manager with SQLite."""

    _instance: Optional["AdminDatabase"] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None) -> "AdminDatabase":
        """Singleton pattern for database instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection."""
        if self._initialized:
            return

        # Get database path from environment or use default
        self.db_path = db_path or os.environ.get(
            "ADMIN_DB_PATH",
            str(Path(__file__).parent.parent.parent.parent / "data" / "admin" / "admin.db"),
        )

        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._initialized = True

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.conn.execute("PRAGMA foreign_keys = ON")
        return self._local.conn

    @contextmanager
    def get_cursor(self):
        """Get database cursor with automatic commit/rollback."""
        cursor = self._conn.cursor()
        try:
            yield cursor
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cursor.close()

    def init_db(self) -> None:
        """Initialize database tables."""
        with self.get_cursor() as cursor:
            # Admin users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)

            # Refresh tokens table for token rotation and revocation
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    revoked BOOLEAN DEFAULT 0,
                    revoked_at TIMESTAMP,
                    replaced_by_token_hash TEXT,
                    FOREIGN KEY (user_id) REFERENCES admin_users(id) ON DELETE CASCADE
                )
            """)

            # Login attempts table for lockout
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    ip_address TEXT,
                    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN NOT NULL,
                    locked_until TIMESTAMP
                )
            """)

            # Configuration table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    encrypted BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, key)
                )
            """)

            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    username TEXT NOT NULL,
                    target TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    before_value TEXT,
                    after_value TEXT,
                    details TEXT
                )
            """)

            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
                ON admin_refresh_tokens(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires
                ON admin_refresh_tokens(expires_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_login_attempts_username
                ON admin_login_attempts(username, attempted_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_config_category
                ON admin_config(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
                ON admin_audit_log(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_action
                ON admin_audit_log(action)
            """)

            # Users table (for user accounts, separate from admin_users)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    role TEXT DEFAULT 'user',
                    avatar TEXT DEFAULT '',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
            """)


            # Migration: add avatar column if missing
            try:
                cursor.execute("SELECT avatar FROM users LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''")

            # Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    is_public BOOLEAN DEFAULT 0,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Project members table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_members (
                    project_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT DEFAULT 'member',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, user_id)
                )
            """)

    # =========================================================================
    # Admin User Operations
    # =========================================================================

    def create_admin_user(
        self, username: str, password_hash: str
    ) -> Optional[int]:
        """Create a new admin user."""
        with self.get_cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO admin_users (username, password_hash)
                    VALUES (?, ?)
                    """,
                    (username, password_hash),
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    def get_admin_user(self, username: str) -> Optional[dict]:
        """Get admin user by username."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, password_hash, created_at, last_login, is_active
                FROM admin_users
                WHERE username = ?
                """,
                (username,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_admin_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get admin user by ID."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, password_hash, created_at, last_login, is_active
                FROM admin_users
                WHERE id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_last_login(self, username: str) -> None:
        """Update user's last login timestamp."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE admin_users
                SET last_login = CURRENT_TIMESTAMP
                WHERE username = ?
                """,
                (username,),
            )

    def get_admin_user_count(self) -> int:
        """Get total admin user count."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM admin_users")
            return cursor.fetchone()[0]

    def setup_initial_admin(self) -> Optional[str]:
        """
        Setup initial admin user.

        Returns:
            - None if admin already exists or created from env vars
            - Bootstrap token string if bootstrap mode is needed
        """
        # Check if any admin exists
        if self.get_admin_user_count() > 0:
            return None

        # Try to create from environment variables
        env_username = os.environ.get("ADMIN_USERNAME")
        env_password = os.environ.get("ADMIN_PASSWORD")

        if env_username and env_password:
            # Import here to avoid circular dependency
            from .auth import hash_password

            password_hash = hash_password(env_password)
            self.create_admin_user(env_username, password_hash)
            logger.info(f"Initial admin user created from environment: {env_username}")
            return None

        # Generate bootstrap token for first-time setup
        bootstrap_token = secrets.token_urlsafe(32)

        # Store bootstrap token in a file
        bootstrap_dir = Path(self.db_path).parent
        bootstrap_file = bootstrap_dir / ".bootstrap_token"

        # Write with restricted permissions
        bootstrap_file.write_text(bootstrap_token)
        os.chmod(bootstrap_file, 0o600)

        logger.info(
            f"No admin user configured. Bootstrap token generated at: {bootstrap_file}"
        )
        logger.info("Use the bootstrap token to create the initial admin user via API.")

        return bootstrap_token

    def verify_bootstrap_token(self, token: str) -> bool:
        """Verify a bootstrap token."""
        bootstrap_file = Path(self.db_path).parent / ".bootstrap_token"

        if not bootstrap_file.exists():
            return False

        stored_token = bootstrap_file.read_text().strip()
        # Use constant-time comparison
        return secrets.compare_digest(token, stored_token)

    def consume_bootstrap_token(self) -> bool:
        """Remove the bootstrap token after successful setup."""
        bootstrap_file = Path(self.db_path).parent / ".bootstrap_token"

        if bootstrap_file.exists():
            bootstrap_file.unlink()
            return True
        return False


    # =========================================================================
    # User Account Operations (separate from admin_users)
    # =========================================================================

    def create_user(
        self, username: str, password_hash: str,
        display_name: str = None, email: str = None, role: str = "user", avatar: str = "",
    ) -> Optional[int]:
        """Create a new user account."""
        with self.get_cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, display_name, email, role, avatar)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (username, password_hash, display_name, email, role, avatar),
                )
                return cursor.lastrowid
            except Exception:
                return None

    def get_user(self, username: str) -> Optional[dict]:
        """Get user by username."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get user by ID."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_users(self, page: int = 1, limit: int = 20, search: str = None) -> tuple[list[dict], int]:
        """List users with pagination and optional search."""
        offset = (page - 1) * limit
        conditions = []
        params = []
        if search:
            conditions.append("(username LIKE ? OR display_name LIKE ? OR email LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        where = " AND ".join(conditions) if conditions else "1=1"

        with self.get_cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM users WHERE {where}", params)
            total = cursor.fetchone()[0]
            cursor.execute(
                f"SELECT * FROM users WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            )
            items = [dict(row) for row in cursor.fetchall()]
        return items, total

    def update_user(self, user_id: int, **kwargs) -> bool:
        """Update user fields."""
        if not kwargs:
            return False
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        with self.get_cursor() as cursor:
            cursor.execute(f"UPDATE users SET {sets} WHERE id = ?", vals)
            return cursor.rowcount > 0

    def update_user_last_login(self, user_id: int) -> None:
        """Update user last login timestamp."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,),
            )

    def get_user_count(self) -> int:
        """Get total user count."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cursor.rowcount > 0

    def setup_initial_user_admin(self) -> None:
        """Create superadmin user from env vars if users table is empty."""
        if self.get_user_count() > 0:
            return
        import os
        from .auth import hash_password
        username = os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")
        if username and password:
            self.create_user(
                username=username,
                password_hash=hash_password(password),
                role="superadmin",
            )
            logger.info(f"Initial superadmin user created: {username}")

    # =========================================================================
    # Refresh Token Operations
    # =========================================================================

    def store_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> int:
        """Store a new refresh token."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO admin_refresh_tokens (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token_hash, expires_at.isoformat()),
            )
            return cursor.lastrowid

    def store_user_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> int:
        """Store a new user refresh token (no FK constraint)."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_refresh_tokens (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token_hash, expires_at.isoformat()),
            )
            return cursor.lastrowid

    def get_user_refresh_token(self, token_hash: str):
        """Get user refresh token by hash."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM user_refresh_tokens WHERE token_hash = ? AND revoked = 0",
                (token_hash,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def revoke_user_refresh_token(self, token_hash: str) -> bool:
        """Revoke a user refresh token."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE user_refresh_tokens SET revoked = 1, revoked_at = CURRENT_TIMESTAMP WHERE token_hash = ?",
                (token_hash,),
            )
            return cursor.rowcount > 0

    def rotate_user_refresh_token(self, old_hash: str, user_id: int, new_hash: str, expires_at) -> bool:
        """Rotate user refresh token."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE user_refresh_tokens SET revoked = 1, revoked_at = CURRENT_TIMESTAMP, replaced_by_token_hash = ? WHERE token_hash = ?",
                (new_hash, old_hash),
            )
            cursor.execute(
                "INSERT INTO user_refresh_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                (user_id, new_hash, expires_at.isoformat()),
            )
            return True

    def get_refresh_token(self, token_hash: str) -> Optional[dict]:
        """Get refresh token by hash."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, token_hash, created_at, expires_at, revoked, revoked_at
                FROM admin_refresh_tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def revoke_refresh_token(
        self, token_hash: str, replaced_by: Optional[str] = None
    ) -> bool:
        """Revoke a refresh token."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE admin_refresh_tokens
                SET revoked = 1, revoked_at = CURRENT_TIMESTAMP, replaced_by_token_hash = ?
                WHERE token_hash = ? AND revoked = 0
                """,
                (replaced_by, token_hash),
            )
            return cursor.rowcount > 0

    def revoke_all_user_tokens(self, user_id: int) -> int:
        """Revoke all refresh tokens for a user."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE admin_refresh_tokens
                SET revoked = 1, revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND revoked = 0
                """,
                (user_id,),
            )
            return cursor.rowcount

    def cleanup_expired_tokens(self) -> int:
        """Remove expired refresh tokens."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM admin_refresh_tokens
                WHERE expires_at < CURRENT_TIMESTAMP
                OR (revoked = 1 AND revoked_at < datetime('now', '-7 days'))
                """
            )
            return cursor.rowcount

    # =========================================================================
    # Login Attempt Operations
    # =========================================================================

    def record_login_attempt(
        self,
        username: str,
        success: bool,
        ip_address: Optional[str] = None,
        locked_until: Optional[datetime] = None,
    ) -> None:
        """Record a login attempt."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO admin_login_attempts
                (username, ip_address, success, locked_until)
                VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    ip_address,
                    success,
                    locked_until.isoformat() if locked_until else None,
                ),
            )

    def get_recent_failed_attempts(
        self, username: str, minutes: int = 15
    ) -> int:
        """Get count of recent failed login attempts."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM admin_login_attempts
                WHERE username = ?
                AND success = 0
                AND attempted_at > datetime('now', ? || ' minutes')
                """,
                (username, -minutes),
            )
            return cursor.fetchone()[0]

    def get_lockout_info(self, username: str) -> Optional[datetime]:
        """Get lockout expiration time if user is locked."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT locked_until FROM admin_login_attempts
                WHERE username = ?
                AND locked_until IS NOT NULL
                AND locked_until > CURRENT_TIMESTAMP
                ORDER BY locked_until DESC
                LIMIT 1
                """,
                (username,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None

    def clear_login_attempts(self, username: str) -> None:
        """Clear login attempts for a user (after successful login)."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM admin_login_attempts
                WHERE username = ?
                AND attempted_at > datetime('now', '-15 minutes')
                """,
                (username,),
            )

    # =========================================================================
    # Configuration Operations
    # =========================================================================

    def get_config(self, category: str, key: str) -> Optional[dict]:
        """Get a configuration value."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, category, key, value, encrypted, created_at, updated_at
                FROM admin_config
                WHERE category = ? AND key = ?
                """,
                (category, key),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_configs_by_category(self, category: str) -> list[dict]:
        """Get all configurations in a category."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, category, key, value, encrypted, created_at, updated_at
                FROM admin_config
                WHERE category = ?
                ORDER BY key
                """,
                (category,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_configs(self) -> list[dict]:
        """Get all configurations."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, category, key, value, encrypted, created_at, updated_at
                FROM admin_config
                ORDER BY category, key
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def set_config(
        self, category: str, key: str, value: str, encrypted: bool = False
    ) -> None:
        """Set a configuration value."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO admin_config (category, key, value, encrypted)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(category, key)
                DO UPDATE SET value = ?, encrypted = ?, updated_at = CURRENT_TIMESTAMP
                """,
                (category, key, value, encrypted, value, encrypted),
            )

    def delete_config(self, category: str, key: str) -> bool:
        """Delete a configuration."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM admin_config
                WHERE category = ? AND key = ?
                """,
                (category, key),
            )
            return cursor.rowcount > 0

    # =========================================================================
    # Audit Log Operations
    # =========================================================================

    def add_audit_log(
        self,
        action: str,
        username: str,
        target: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        before_value: Optional[str] = None,
        after_value: Optional[str] = None,
        details: Optional[str] = None,
    ) -> int:
        """Add an audit log entry."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO admin_audit_log
                (action, username, target, ip_address, user_agent, before_value, after_value, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    username,
                    target,
                    ip_address,
                    user_agent,
                    before_value,
                    after_value,
                    details,
                ),
            )
            return cursor.lastrowid

    def get_audit_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[str] = None,
        username: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get audit logs with filtering and pagination."""
        conditions = []
        params = []

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
        if action:
            conditions.append("action = ?")
            params.append(action)
        if username:
            conditions.append("username = ?")
            params.append(username)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self.get_cursor() as cursor:
            # Get total count
            cursor.execute(
                f"SELECT COUNT(*) FROM admin_audit_log WHERE {where_clause}",
                params,
            )
            total = cursor.fetchone()[0]

            # Get paginated results
            cursor.execute(
                f"""
                SELECT id, timestamp, action, username, target,
                       ip_address, user_agent, before_value, after_value, details
                FROM admin_audit_log
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            )
            items = [dict(row) for row in cursor.fetchall()]

            return items, total

    def cleanup_old_audit_logs(self, days: int = 90) -> int:
        """Clean up audit logs older than specified days."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM admin_audit_log
                WHERE timestamp < datetime('now', ? || ' days')
                """,
                (-days,),
            )
            return cursor.rowcount

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None
