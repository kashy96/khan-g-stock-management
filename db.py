"""Database layer for KHAN G Stationary stock management (v3 - locations).

Data model:
  products      -> the item family (e.g. "Ballpoint Pen")
  variants      -> each sellable version (e.g. "Blue", "Red") with its own
                   cost, price, quantity and a link to a LOCATION
  locations     -> managed list of shelves/racks, each with an optional
                   photo (stored in the database so it is shared over LAN)
  transactions  -> every stock IN / OUT, recorded against a variant

Engines (config.json):
  - "sqlite" : single-PC use, zero setup (default)
  - "mysql"  : shared database on the shop's main PC for LAN use
               (requires:  pip install pymysql)

Older SQLite databases are migrated automatically on first run:
  v1 (no variants)        -> every product becomes one "Standard" variant
  v2 (text locations)     -> distinct location texts become location records
"""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta

if getattr(sys, "frozen", False):
    # Running as a packaged .exe (PyInstaller) - keep data next to the exe,
    # not inside its temporary extraction folder.
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "engine": "sqlite",
    "sqlite_file": "khan_g_stock.db",
    "mysql": {
        "host": "192.168.1.100",
        "port": 3306,
        "user": "khang",
        "password": "change-me",
        "database": "khan_g_stock",
    },
}

DATE_FMT = "%Y-%m-%d %H:%M:%S"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000
    ).hex()
    return salt, digest


SCHEMA_SQLITE = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        full_name TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT 'staff',
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        note TEXT NOT NULL DEFAULT '',
        image BLOB,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL DEFAULT 'Standard',
        cost REAL NOT NULL DEFAULT 0,
        price REAL NOT NULL DEFAULT 0,
        quantity INTEGER NOT NULL DEFAULT 0,
        location_id INTEGER,
        low_stock_level INTEGER NOT NULL DEFAULT 5,
        created_at TEXT NOT NULL,
        UNIQUE (product_id, name)
    )""",
    """CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_cost REAL NOT NULL,
        unit_price REAL NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""",
]

SCHEMA_MYSQL = [
    """CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(64) NOT NULL UNIQUE,
        full_name VARCHAR(128) NOT NULL DEFAULT '',
        role VARCHAR(16) NOT NULL DEFAULT 'staff',
        salt VARCHAR(64) NOT NULL,
        password_hash VARCHAR(128) NOT NULL,
        created_at DATETIME NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(128) NOT NULL UNIQUE,
        category VARCHAR(64) NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS locations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(64) NOT NULL UNIQUE,
        note VARCHAR(255) NOT NULL DEFAULT '',
        image LONGBLOB,
        created_at DATETIME NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS variants (
        id INT AUTO_INCREMENT PRIMARY KEY,
        product_id INT NOT NULL,
        name VARCHAR(64) NOT NULL DEFAULT 'Standard',
        cost DOUBLE NOT NULL DEFAULT 0,
        price DOUBLE NOT NULL DEFAULT 0,
        quantity INT NOT NULL DEFAULT 0,
        location_id INT,
        low_stock_level INT NOT NULL DEFAULT 5,
        created_at DATETIME NOT NULL,
        UNIQUE KEY uq_variant (product_id, name)
    )""",
    """CREATE TABLE IF NOT EXISTS transactions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        variant_id INT NOT NULL,
        user_id INT NOT NULL,
        type VARCHAR(8) NOT NULL,
        quantity INT NOT NULL,
        unit_cost DOUBLE NOT NULL,
        unit_price DOUBLE NOT NULL,
        note VARCHAR(255) NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL
    )""",
]


class Database:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.engine = self.config.get("engine", "sqlite")
        if self.engine == "mysql":
            import pymysql  # pip install pymysql

            m = self.config["mysql"]
            self.conn = pymysql.connect(
                host=m["host"], port=int(m.get("port", 3306)),
                user=m["user"], password=m["password"],
                database=m["database"], autocommit=False,
            )
        else:
            path = os.path.join(APP_DIR, self.config.get("sqlite_file", "khan_g_stock.db"))
            self.conn = sqlite3.connect(path)
            self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._ensure_default_admin()

    # -- low-level helpers ---------------------------------------------------

    def _sql(self, query):
        """sqlite uses ? placeholders, pymysql uses %s."""
        return query.replace("?", "%s") if self.engine == "mysql" else query

    def execute(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(self._sql(query), params)
        return cur

    def fetchall(self, query, params=()):
        cur = self.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def fetchone(self, query, params=()):
        cur = self.execute(query, params)
        row = cur.fetchone()
        cur.close()
        return row

    def commit(self):
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    @staticmethod
    def now():
        return datetime.now().strftime(DATE_FMT)

    # -- schema / bootstrap / migration ---------------------------------------

    def _sqlite_version(self):
        rows = self.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        names = {r[0] for r in rows}
        if "products" in names and "variants" not in names:
            return 1
        if "variants" in names and "locations" not in names:
            return 2
        return 3

    def _init_schema(self):
        version = self._sqlite_version() if self.engine == "sqlite" else 3
        if version == 1:
            self.execute("ALTER TABLE products RENAME TO products_v1")
            self.execute("ALTER TABLE transactions RENAME TO transactions_v1")
        schema = SCHEMA_MYSQL if self.engine == "mysql" else SCHEMA_SQLITE
        for stmt in schema:
            self.execute(stmt)
        if version == 1:
            self.execute(
                "INSERT INTO products (id, name, category, created_at) "
                "SELECT id, name, category, created_at FROM products_v1")
            self.execute(
                "INSERT INTO variants (id, product_id, name, cost, price, quantity, "
                "location_id, low_stock_level, created_at) "
                "SELECT id, id, 'Standard', cost, price, quantity, NULL, "
                "low_stock_level, created_at FROM products_v1")
            self.execute(
                "INSERT INTO transactions (id, variant_id, user_id, type, quantity, "
                "unit_cost, unit_price, note, created_at) "
                "SELECT id, product_id, user_id, type, quantity, unit_cost, "
                "unit_price, note, created_at FROM transactions_v1")
            self.execute("DROP TABLE products_v1")
            self.execute("DROP TABLE transactions_v1")
        elif version == 2:
            # v2 stored the location as free text on each variant
            self.execute("ALTER TABLE variants ADD COLUMN location_id INTEGER")
            self.execute(
                "INSERT INTO locations (name, note, created_at) "
                "SELECT DISTINCT TRIM(location), '', ? FROM variants "
                "WHERE TRIM(location) != ''", (self.now(),))
            self.execute(
                "UPDATE variants SET location_id = (SELECT id FROM locations l "
                "WHERE l.name = TRIM(variants.location))")
        self.commit()

    def _ensure_default_admin(self):
        row = self.fetchone("SELECT COUNT(*) FROM users")
        if row and row[0] == 0:
            self.add_user("admin", "admin123", "Administrator", "admin")

    # -- users ----------------------------------------------------------------

    def verify_user(self, username, password):
        row = self.fetchone(
            "SELECT id, username, full_name, role, salt, password_hash "
            "FROM users WHERE username = ?", (username,))
        if not row:
            return None
        _, digest = hash_password(password, row[4])
        if digest != row[5]:
            return None
        return {"id": row[0], "username": row[1], "full_name": row[2], "role": row[3]}

    def add_user(self, username, password, full_name="", role="staff"):
        salt, digest = hash_password(password)
        self.execute(
            "INSERT INTO users (username, full_name, role, salt, password_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username.strip(), full_name.strip(), role, salt, digest, self.now()))
        self.commit()

    def list_users(self):
        return self.fetchall(
            "SELECT id, username, full_name, role, created_at FROM users ORDER BY username")

    def delete_user(self, user_id):
        self.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.commit()

    def reset_password(self, user_id, new_password):
        salt, digest = hash_password(new_password)
        self.execute(
            "UPDATE users SET salt = ?, password_hash = ? WHERE id = ?",
            (salt, digest, user_id))
        self.commit()

    def count_admins(self):
        row = self.fetchone("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        return row[0] if row else 0

    # -- backup ------------------------------------------------------------------

    def backup_sqlite(self, dest_path):
        """Safe live backup of a SQLite database to dest_path (includes
        photos, since they are stored inside the database). Not available
        in MySQL mode - use mysqldump there instead (see README)."""
        if self.engine != "sqlite":
            raise RuntimeError("Backup is only available in single-PC (SQLite) mode. "
                               "For the shared network setup, back up MySQL with "
                               "mysqldump - see README.md.")
        dest = sqlite3.connect(dest_path)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()

    # -- locations ---------------------------------------------------------------

    def add_location(self, name, note="", image=None):
        cur = self.execute(
            "INSERT INTO locations (name, note, image, created_at) VALUES (?, ?, ?, ?)",
            (name.strip(), note.strip(), image, self.now()))
        location_id = cur.lastrowid
        cur.close()
        self.commit()
        return location_id

    def update_location(self, location_id, name, note, image=None, replace_image=False):
        if replace_image:
            self.execute(
                "UPDATE locations SET name = ?, note = ?, image = ? WHERE id = ?",
                (name.strip(), note.strip(), image, location_id))
        else:
            self.execute(
                "UPDATE locations SET name = ?, note = ? WHERE id = ?",
                (name.strip(), note.strip(), location_id))
        self.commit()

    def delete_location(self, location_id):
        """Items at this location are kept and become '(no location)'."""
        self.execute("UPDATE variants SET location_id = NULL WHERE location_id = ?",
                     (location_id,))
        self.execute("DELETE FROM locations WHERE id = ?", (location_id,))
        self.commit()

    def get_location(self, location_id):
        """(id, name, note, image_bytes_or_None)"""
        return self.fetchone(
            "SELECT id, name, note, image FROM locations WHERE id = ?", (location_id,))

    def list_locations(self):
        """Rows: (id, name, note, item_count, total_units, has_image)"""
        return self.fetchall(
            "SELECT l.id, l.name, l.note, "
            "(SELECT COUNT(*) FROM variants v WHERE v.location_id = l.id), "
            "(SELECT COALESCE(SUM(quantity), 0) FROM variants v WHERE v.location_id = l.id), "
            "CASE WHEN l.image IS NULL THEN 0 ELSE 1 END "
            "FROM locations l ORDER BY l.name")

    def unassigned_summary(self):
        """(item_count, total_units) for variants without a location."""
        return self.fetchone(
            "SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM variants "
            "WHERE location_id IS NULL")

    def location_items(self, location_id):
        """Items at a location (None = unassigned).
        Rows: (product, variant, qty, price, cost, low)"""
        base = ("SELECT p.name, v.name, v.quantity, v.price, v.cost, v.low_stock_level "
                "FROM variants v JOIN products p ON p.id = v.product_id ")
        if location_id is None:
            return self.fetchall(base + "WHERE v.location_id IS NULL "
                                        "ORDER BY p.name, v.name")
        return self.fetchall(base + "WHERE v.location_id = ? ORDER BY p.name, v.name",
                             (location_id,))

    def search_location_ids(self, text):
        """Location ids (and possibly None) holding items that match the text."""
        like = f"%{text.strip()}%"
        rows = self.fetchall(
            "SELECT DISTINCT v.location_id FROM variants v "
            "JOIN products p ON p.id = v.product_id "
            "WHERE p.name LIKE ? OR v.name LIKE ? OR p.category LIKE ?",
            (like, like, like))
        return {r[0] for r in rows}

    # -- products & variants ---------------------------------------------------

    def add_product(self, name, category):
        cur = self.execute(
            "INSERT INTO products (name, category, created_at) VALUES (?, ?, ?)",
            (name.strip(), category.strip(), self.now()))
        product_id = cur.lastrowid
        cur.close()
        self.commit()
        return product_id

    def update_product(self, product_id, name, category):
        self.execute("UPDATE products SET name = ?, category = ? WHERE id = ?",
                     (name.strip(), category.strip(), product_id))
        self.commit()

    def delete_product(self, product_id):
        self.execute(
            "DELETE FROM transactions WHERE variant_id IN "
            "(SELECT id FROM variants WHERE product_id = ?)", (product_id,))
        self.execute("DELETE FROM variants WHERE product_id = ?", (product_id,))
        self.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.commit()

    def get_product(self, product_id):
        return self.fetchone(
            "SELECT id, name, category FROM products WHERE id = ?", (product_id,))

    def add_variant(self, product_id, name, cost, price, quantity, location_id,
                    low_stock_level, user_id):
        cur = self.execute(
            "INSERT INTO variants (product_id, name, cost, price, quantity, "
            "location_id, low_stock_level, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (product_id, name.strip() or "Standard", cost, price, 0,
             location_id, low_stock_level, self.now()))
        variant_id = cur.lastrowid
        cur.close()
        if quantity > 0:
            self._record_txn_raw(variant_id, user_id, "IN", quantity,
                                 cost, price, "Opening stock")
        self.commit()
        return variant_id

    def update_variant(self, variant_id, name, cost, price, location_id,
                       low_stock_level):
        self.execute(
            "UPDATE variants SET name = ?, cost = ?, price = ?, location_id = ?, "
            "low_stock_level = ? WHERE id = ?",
            (name.strip() or "Standard", cost, price, location_id,
             low_stock_level, variant_id))
        self.commit()

    def delete_variant(self, variant_id):
        self.execute("DELETE FROM transactions WHERE variant_id = ?", (variant_id,))
        self.execute("DELETE FROM variants WHERE id = ?", (variant_id,))
        self.commit()

    def get_variant(self, variant_id):
        """(id, product_id, product_name, variant_name, cost, price, qty,
            location_id, location_name, low)"""
        return self.fetchone(
            "SELECT v.id, v.product_id, p.name, v.name, v.cost, v.price, v.quantity, "
            "v.location_id, COALESCE(l.name, ''), v.low_stock_level "
            "FROM variants v "
            "JOIN products p ON p.id = v.product_id "
            "LEFT JOIN locations l ON l.id = v.location_id "
            "WHERE v.id = ?", (variant_id,))

    def count_variants(self, product_id):
        row = self.fetchone("SELECT COUNT(*) FROM variants WHERE product_id = ?",
                            (product_id,))
        return row[0] if row else 0

    def products_with_variants(self, search=""):
        """Rows: (p_id, p_name, category, v_id, v_name, cost, price, qty,
        location_name, low). v_* fields are NULL for a product without variants."""
        base = ("SELECT p.id, p.name, p.category, v.id, v.name, v.cost, v.price, "
                "v.quantity, COALESCE(l.name, ''), v.low_stock_level "
                "FROM products p "
                "LEFT JOIN variants v ON v.product_id = p.id "
                "LEFT JOIN locations l ON l.id = v.location_id ")
        if search.strip():
            like = f"%{search.strip()}%"
            return self.fetchall(
                base + "WHERE p.name LIKE ? OR p.category LIKE ? OR v.name LIKE ? "
                "OR l.name LIKE ? ORDER BY p.name, v.name",
                (like, like, like, like))
        return self.fetchall(base + "ORDER BY p.name, v.name")

    def list_variants(self, search=""):
        """Rows: (v_id, product_name, variant_name, qty, location_name, cost,
        price, low)"""
        base = ("SELECT v.id, p.name, v.name, v.quantity, COALESCE(l.name, ''), "
                "v.cost, v.price, v.low_stock_level "
                "FROM variants v "
                "JOIN products p ON p.id = v.product_id "
                "LEFT JOIN locations l ON l.id = v.location_id ")
        if search.strip():
            like = f"%{search.strip()}%"
            return self.fetchall(
                base + "WHERE p.name LIKE ? OR v.name LIKE ? OR l.name LIKE ? "
                "OR p.category LIKE ? ORDER BY p.name, v.name",
                (like, like, like, like))
        return self.fetchall(base + "ORDER BY p.name, v.name")

    # -- stock transactions ------------------------------------------------------

    def _record_txn_raw(self, variant_id, user_id, ttype, qty, unit_cost, unit_price, note):
        self.execute(
            "INSERT INTO transactions (variant_id, user_id, type, quantity, unit_cost, "
            "unit_price, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (variant_id, user_id, ttype, qty, unit_cost, unit_price, note.strip(), self.now()))
        delta = qty if ttype == "IN" else -qty
        self.execute("UPDATE variants SET quantity = quantity + ? WHERE id = ?",
                     (delta, variant_id))

    def record_txn(self, variant_id, user_id, ttype, qty, note=""):
        """Stock IN or OUT for a variant. Returns error message, or None on success."""
        if qty <= 0:
            return "Quantity must be greater than zero."
        variant = self.get_variant(variant_id)
        if not variant:
            return "Product variant not found."
        if ttype == "OUT" and variant[6] < qty:
            return f"Not enough stock. Available: {variant[6]}"
        self._record_txn_raw(variant_id, user_id, ttype, qty, variant[4], variant[5], note)
        self.commit()
        return None

    def recent_txns(self, limit=100):
        return self.fetchall(
            "SELECT t.created_at, p.name, v.name, COALESCE(l.name, ''), t.type, "
            "t.quantity, t.unit_price, t.quantity * t.unit_price, u.username, t.note "
            "FROM transactions t "
            "JOIN variants v ON v.id = t.variant_id "
            "JOIN products p ON p.id = v.product_id "
            "LEFT JOIN locations l ON l.id = v.location_id "
            "JOIN users u ON u.id = t.user_id "
            "ORDER BY t.id DESC LIMIT " + str(int(limit)))

    # -- reports -------------------------------------------------------------------

    @staticmethod
    def period_range(period):
        """Returns (start, end) datetimes, end exclusive."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "Today":
            return today, today + timedelta(days=1)
        if period == "Yesterday":
            return today - timedelta(days=1), today
        if period == "This Week":
            start = today - timedelta(days=today.weekday())
            return start, start + timedelta(days=7)
        if period == "Last Week":
            start = today - timedelta(days=today.weekday() + 7)
            return start, start + timedelta(days=7)
        if period == "This Month":
            start = today.replace(day=1)
            nxt = (start + timedelta(days=32)).replace(day=1)
            return start, nxt
        if period == "Last Month":
            first_this = today.replace(day=1)
            start = (first_this - timedelta(days=1)).replace(day=1)
            return start, first_this
        if period == "This Year":
            start = today.replace(month=1, day=1)
            return start, start.replace(year=start.year + 1)
        return datetime(2000, 1, 1), today + timedelta(days=1)  # All Time

    def report_summary(self, start, end):
        row = self.fetchone(
            "SELECT "
            "COALESCE(SUM(CASE WHEN type='IN' THEN quantity END), 0), "
            "COALESCE(SUM(CASE WHEN type='OUT' THEN quantity END), 0), "
            "COALESCE(SUM(CASE WHEN type='OUT' THEN quantity * unit_price END), 0), "
            "COALESCE(SUM(CASE WHEN type='OUT' THEN quantity * unit_cost END), 0), "
            "COALESCE(SUM(CASE WHEN type='OUT' THEN quantity * (unit_price - unit_cost) END), 0) "
            "FROM transactions WHERE created_at >= ? AND created_at < ?",
            (start, end))
        return {
            "stock_in": row[0], "items_sold": row[1],
            "revenue": row[2], "cost": row[3], "profit": row[4],
        }

    _TXN_AGG = (
        "COALESCE(SUM(CASE WHEN t.type='IN' THEN t.quantity END), 0), "
        "COALESCE(SUM(CASE WHEN t.type='OUT' THEN t.quantity END), 0), "
        "COALESCE(SUM(CASE WHEN t.type='OUT' THEN t.quantity * t.unit_price END), 0), "
        "COALESCE(SUM(CASE WHEN t.type='OUT' THEN t.quantity * (t.unit_price - t.unit_cost) END), 0) ")

    def report_by_product(self, start, end):
        return self.fetchall(
            "SELECT p.name, " + self._TXN_AGG + ", "
            "(SELECT COALESCE(SUM(quantity), 0) FROM variants WHERE product_id = p.id) "
            "FROM transactions t "
            "JOIN variants v ON v.id = t.variant_id "
            "JOIN products p ON p.id = v.product_id "
            "WHERE t.created_at >= ? AND t.created_at < ? "
            "GROUP BY p.id, p.name ORDER BY p.name",
            (start, end))

    def report_by_variant(self, start, end):
        return self.fetchall(
            "SELECT p.name, v.name, COALESCE(l.name, ''), " + self._TXN_AGG +
            ", v.quantity "
            "FROM transactions t "
            "JOIN variants v ON v.id = t.variant_id "
            "JOIN products p ON p.id = v.product_id "
            "LEFT JOIN locations l ON l.id = v.location_id "
            "WHERE t.created_at >= ? AND t.created_at < ? "
            "GROUP BY v.id, p.name, v.name, l.name, v.quantity "
            "ORDER BY p.name, v.name",
            (start, end))

    def report_by_day(self, start, end):
        day_expr = ("DATE(created_at)" if self.engine == "mysql"
                    else "substr(created_at, 1, 10)")
        return self.fetchall(
            f"SELECT {day_expr} AS day, "
            "COALESCE(SUM(CASE WHEN type='IN' THEN quantity END), 0), "
            "COALESCE(SUM(CASE WHEN type='OUT' THEN quantity END), 0), "
            "COALESCE(SUM(CASE WHEN type='OUT' THEN quantity * unit_price END), 0), "
            "COALESCE(SUM(CASE WHEN type='OUT' THEN quantity * (unit_price - unit_cost) END), 0) "
            "FROM transactions WHERE created_at >= ? AND created_at < ? "
            f"GROUP BY {day_expr} ORDER BY day",
            (start, end))

    def report_transactions(self, start, end):
        return self.fetchall(
            "SELECT t.created_at, p.name, v.name, t.type, t.quantity, t.unit_cost, "
            "t.unit_price, t.quantity * t.unit_price, "
            "CASE WHEN t.type='OUT' THEN t.quantity * (t.unit_price - t.unit_cost) ELSE 0 END, "
            "u.username, t.note "
            "FROM transactions t "
            "JOIN variants v ON v.id = t.variant_id "
            "JOIN products p ON p.id = v.product_id "
            "JOIN users u ON u.id = t.user_id "
            "WHERE t.created_at >= ? AND t.created_at < ? ORDER BY t.id",
            (start, end))

    def top_sellers(self, start, end, limit=8):
        return self.fetchall(
            "SELECT p.name, v.name, "
            "COALESCE(SUM(t.quantity), 0), "
            "COALESCE(SUM(t.quantity * t.unit_price), 0) "
            "FROM transactions t "
            "JOIN variants v ON v.id = t.variant_id "
            "JOIN products p ON p.id = v.product_id "
            "WHERE t.type = 'OUT' AND t.created_at >= ? AND t.created_at < ? "
            "GROUP BY v.id, p.name, v.name "
            "ORDER BY 4 DESC LIMIT " + str(int(limit)),
            (start, end))

    # -- dashboard --------------------------------------------------------------

    def dashboard_stats(self):
        products = self.fetchone("SELECT COUNT(*) FROM products")
        totals = self.fetchone(
            "SELECT COUNT(*), COALESCE(SUM(quantity), 0), "
            "COALESCE(SUM(quantity * cost), 0), "
            "COALESCE(SUM(quantity * (price - cost)), 0) FROM variants")
        start, end = self.period_range("Today")
        today = self.report_summary(start.strftime(DATE_FMT), end.strftime(DATE_FMT))
        low = self.fetchall(
            "SELECT p.name, v.name, COALESCE(l.name, ''), v.quantity, v.low_stock_level "
            "FROM variants v "
            "JOIN products p ON p.id = v.product_id "
            "LEFT JOIN locations l ON l.id = v.location_id "
            "WHERE v.quantity <= v.low_stock_level ORDER BY v.quantity")
        m_start, m_end = self.period_range("This Month")
        top = self.top_sellers(m_start.strftime(DATE_FMT), m_end.strftime(DATE_FMT))
        return {
            "product_count": products[0],
            "variant_count": totals[0],
            "stock_units": totals[1],
            "stock_value": totals[2],
            "potential_profit": totals[3],
            "today": today,
            "low_stock": low,
            "top_sellers": top,
        }
