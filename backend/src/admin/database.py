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

            # Project stages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_stages (
                    id TEXT PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    template_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    sort_order INTEGER NOT NULL,
                    status TEXT DEFAULT 'locked',
                    prerequisites TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    stage_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    current_version INTEGER DEFAULT 1,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (stage_id) REFERENCES project_stages(id) ON DELETE CASCADE
                )
            """)

            # Document versions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_versions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    diff_summary TEXT DEFAULT '',
                    source_type TEXT DEFAULT 'manual',
                    source_id TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)

            # Discussion outputs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discussion_outputs (
                    id TEXT PRIMARY KEY,
                    discussion_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    output_type TEXT DEFAULT 'new_doc',
                    status TEXT DEFAULT 'draft',
                    adopted_document_id TEXT,
                    adopted_version INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    # Stage Operations
    # =========================================================================

    DEFAULT_STAGES = [
        {"template_id": "concept",       "name": "概念孵化",         "sort": 1, "prereqs": []},
        {"template_id": "core-gameplay", "name": "核心玩法 GDD",     "sort": 2, "prereqs": ["concept"]},
        {"template_id": "art-style",     "name": "美术风格定义",      "sort": 3, "prereqs": ["concept"]},
        {"template_id": "tech-prototype","name": "技术选型 & 原型",   "sort": 4, "prereqs": ["concept"]},
        {"template_id": "system-design", "name": "系统设计文档",      "sort": 5, "prereqs": ["core-gameplay"]},
        {"template_id": "numbers",       "name": "数值框架",         "sort": 6, "prereqs": ["core-gameplay"]},
        {"template_id": "ui-ux",         "name": "UI/UX 界面设计",   "sort": 7, "prereqs": ["core-gameplay"]},
        {"template_id": "level-content", "name": "关卡/内容规划",     "sort": 8, "prereqs": ["system-design"]},
        {"template_id": "art-assets",    "name": "美术资源需求清单",   "sort": 9, "prereqs": ["art-style"]},
    ]


    def get_or_create_project_db_id(self, slug: str, name: str = "", created_by: int = 0) -> int:
        """Get the integer DB id for a project slug, creating a row if needed."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id FROM projects WHERE slug = ?", (slug,))
            row = cursor.fetchone()
            if row:
                return row["id"] if isinstance(row, dict) or hasattr(row, 'keys') else row[0]
            cursor.execute(
                "INSERT INTO projects (slug, name, created_by) VALUES (?, ?, ?)",
                (slug, name or slug, created_by)
            )
            return cursor.lastrowid


    def resolve_project_id(self, project_id) -> int:
        """Resolve a project slug or integer id to the DB integer id."""
        if isinstance(project_id, int):
            return project_id
        try:
            return int(project_id)
        except (ValueError, TypeError):
            pass
        return self.get_or_create_project_db_id(str(project_id))

    def init_project_stages(self, project_id) -> list[dict]:
        """Initialize default stages for a new project. Returns created stages."""
        import uuid, json
        project_id = self.resolve_project_id(project_id)
        stages = []
        with self.get_cursor() as cursor:
            for s in self.DEFAULT_STAGES:
                stage_id = str(uuid.uuid4())
                status = "active" if not s["prereqs"] else "locked"
                cursor.execute(
                    """INSERT INTO project_stages (id, project_id, template_id, name, sort_order, status, prerequisites)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (stage_id, project_id, s["template_id"], s["name"], s["sort"], status, json.dumps(s["prereqs"]))
                )
                stages.append({"id": stage_id, "template_id": s["template_id"], "name": s["name"],
                               "sort_order": s["sort"], "status": status, "prerequisites": s["prereqs"]})
        return stages

    def get_project_stages(self, project_id) -> list[dict]:
        """Get all stages for a project, with computed status."""
        import json
        project_id = self.resolve_project_id(project_id)
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM project_stages WHERE project_id = ? ORDER BY sort_order", (project_id,)
            )
            rows = cursor.fetchall()
            stages = []
            for r in rows:
                d = dict(r)
                d["prerequisites"] = json.loads(d.get("prerequisites", "[]"))
                stages.append(d)
            # Compute effective status based on prerequisites
            status_map = {s["template_id"]: s["status"] for s in stages}
            for s in stages:
                if s["status"] == "locked":
                    prereqs_met = all(status_map.get(p) == "completed" for p in s["prerequisites"])
                    if prereqs_met:
                        s["status"] = "active"
                        # Persist the unlock
                        cursor.execute("UPDATE project_stages SET status = 'active' WHERE id = ?", (s["id"],))
            return stages

    def update_stage(self, stage_id: str, **kwargs) -> bool:
        if not kwargs:
            return False
        allowed = {"name", "description", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [stage_id]
        with self.get_cursor() as cursor:
            cursor.execute(f"UPDATE project_stages SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
            return cursor.rowcount > 0

    def complete_stage(self, stage_id: str) -> dict:
        """Mark stage as completed and return newly unlocked stages."""
        with self.get_cursor() as cursor:
            cursor.execute("UPDATE project_stages SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (stage_id,))
            cursor.execute("SELECT project_id FROM project_stages WHERE id = ?", (stage_id,))
            row = cursor.fetchone()
            if not row:
                return {"unlocked": []}
        # Re-compute will auto-unlock dependents
        stages = self.get_project_stages(dict(row)["project_id"])
        unlocked = [s for s in stages if s["status"] == "active"]
        return {"unlocked": unlocked}

    # =========================================================================
    # Document Operations
    # =========================================================================

    def create_document(self, project_id, stage_id: str, title: str, content: str = "", created_by: int = None) -> dict:
        project_id = self.resolve_project_id(project_id)
        import uuid
        doc_id = str(uuid.uuid4())
        ver_id = str(uuid.uuid4())
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO documents (id, project_id, stage_id, title, content, current_version, created_by)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (doc_id, project_id, stage_id, title, content, created_by)
            )
            cursor.execute(
                """INSERT INTO document_versions (id, document_id, version, content, source_type, created_by)
                   VALUES (?, ?, 1, ?, 'manual', ?)""",
                (ver_id, doc_id, content, created_by)
            )
        return {"id": doc_id, "title": title, "current_version": 1}

    def get_document(self, doc_id: str) -> Optional[dict]:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_stage_documents(self, stage_id: str) -> list[dict]:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM documents WHERE stage_id = ? ORDER BY created_at", (stage_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_project_documents(self, project_id) -> list[dict]:
        project_id = self.resolve_project_id(project_id)
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM documents WHERE project_id = ? ORDER BY created_at", (project_id,))
            return [dict(r) for r in cursor.fetchall()]

    def update_document(self, doc_id: str, title: str = None, content: str = None,
                        source_type: str = "manual", source_id: str = None, updated_by: int = None) -> Optional[dict]:
        """Update document content, creating a new version."""
        import uuid
        doc = self.get_document(doc_id)
        if not doc:
            return None
        new_version = doc["current_version"] + 1
        with self.get_cursor() as cursor:
            updates = ["updated_at = CURRENT_TIMESTAMP"]
            params = []
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if content is not None:
                updates.append("content = ?")
                params.append(content)
                updates.append("current_version = ?")
                params.append(new_version)
                # Create version record
                ver_id = str(uuid.uuid4())
                cursor.execute(
                    """INSERT INTO document_versions (id, document_id, version, content, source_type, source_id, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ver_id, doc_id, new_version, content, source_type, source_id, updated_by)
                )
            params.append(doc_id)
            cursor.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id = ?", params)
        return self.get_document(doc_id)

    def get_document_versions(self, doc_id: str) -> list[dict]:
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM document_versions WHERE document_id = ? ORDER BY version DESC", (doc_id,)
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_document_version(self, doc_id: str, version: int) -> Optional[dict]:
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM document_versions WHERE document_id = ? AND version = ?", (doc_id, version)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def revert_document(self, doc_id: str, version: int, reverted_by: int = None) -> Optional[dict]:
        """Revert document to a specific version (creates new version with old content)."""
        ver = self.get_document_version(doc_id, version)
        if not ver:
            return None
        return self.update_document(doc_id, content=ver["content"], source_type="manual", updated_by=reverted_by)

    # =========================================================================
    # Discussion Output Operations
    # =========================================================================

    def create_discussion_output(self, discussion_id: str, title: str, content: str,
                                  output_type: str = "new_doc") -> dict:
        import uuid
        oid = str(uuid.uuid4())
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO discussion_outputs (id, discussion_id, title, content, output_type)
                   VALUES (?, ?, ?, ?, ?)""",
                (oid, discussion_id, title, content, output_type)
            )
        return {"id": oid, "title": title, "status": "draft"}

    def get_discussion_outputs(self, discussion_id: str) -> list[dict]:
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM discussion_outputs WHERE discussion_id = ? ORDER BY created_at", (discussion_id,)
            )
            return [dict(r) for r in cursor.fetchall()]

    def adopt_output(self, output_id: str, document_id: str, version: int) -> bool:
        with self.get_cursor() as cursor:
            cursor.execute(
                """UPDATE discussion_outputs
                   SET status = 'adopted', adopted_document_id = ?, adopted_version = ?
                   WHERE id = ?""",
                (document_id, version, output_id)
            )
            return cursor.rowcount > 0

    def dismiss_output(self, output_id: str) -> bool:
        with self.get_cursor() as cursor:
            cursor.execute("UPDATE discussion_outputs SET status = 'dismissed' WHERE id = ?", (output_id,))
            return cursor.rowcount > 0

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
