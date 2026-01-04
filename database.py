import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = 'cloudtunnel.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 项目表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 部署表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id TEXT,
            subdomain TEXT NOT NULL,
            domain TEXT NOT NULL,
            port INTEGER NOT NULL,
            status TEXT DEFAULT 'stopped',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    # 日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 设置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            key TEXT NOT NULL,
            value TEXT,
            UNIQUE(user_id, key),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# ============ 用户管理 ============

def create_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if user and check_password_hash(user['password_hash'], password):
        return dict(user)
    return None

def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_password(user_id, old_password, new_password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    if not user or not check_password_hash(user['password_hash'], old_password):
        conn.close()
        return False
    new_hash = generate_password_hash(new_password)
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
    conn.commit()
    conn.close()
    return True

# ============ 项目管理 ============

def create_project(user_id, name, description=''):
    import uuid
    project_id = str(uuid.uuid4())[:8]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO projects (id, user_id, name, description) VALUES (?, ?, ?, ?)',
        (project_id, user_id, name, description)
    )
    conn.commit()
    conn.close()
    return project_id

def get_projects(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    )
    projects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return projects

def get_project(project_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM projects WHERE id = ? AND user_id = ?',
        (project_id, user_id)
    )
    project = cursor.fetchone()
    conn.close()
    return dict(project) if project else None

def delete_project(project_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM projects WHERE id = ? AND user_id = ?',
        (project_id, user_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

# ============ 部署管理 ============

def create_deployment(user_id, project_id, subdomain, domain, port):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO deployments (user_id, project_id, subdomain, domain, port, status) 
           VALUES (?, ?, ?, ?, ?, 'stopped')''',
        (user_id, project_id, subdomain, domain, port)
    )
    conn.commit()
    deploy_id = cursor.lastrowid
    conn.close()
    return deploy_id

def get_deployments(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, p.name as project_name 
        FROM deployments d 
        LEFT JOIN projects p ON d.project_id = p.id 
        WHERE d.user_id = ? 
        ORDER BY d.created_at DESC
    ''', (user_id,))
    deployments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return deployments

def get_deployment(deploy_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM deployments WHERE id = ? AND user_id = ?',
        (deploy_id, user_id)
    )
    deployment = cursor.fetchone()
    conn.close()
    return dict(deployment) if deployment else None

def update_deployment_status(deploy_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE deployments SET status = ? WHERE id = ?',
        (status, deploy_id)
    )
    conn.commit()
    conn.close()

def delete_deployment(deploy_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM deployments WHERE id = ? AND user_id = ?',
        (deploy_id, user_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

# ============ 日志管理 ============

def add_log(user_id, level, message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO logs (user_id, level, message) VALUES (?, ?, ?)',
        (user_id, level, message)
    )
    conn.commit()
    conn.close()

def get_logs(user_id, level=None, limit=100, offset=0):
    conn = get_db()
    cursor = conn.cursor()
    if level:
        cursor.execute(
            '''SELECT * FROM logs WHERE user_id = ? AND level = ? 
               ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            (user_id, level, limit, offset)
        )
    else:
        cursor.execute(
            '''SELECT * FROM logs WHERE user_id = ? 
               ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            (user_id, limit, offset)
        )
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs

def get_logs_count(user_id, level=None):
    conn = get_db()
    cursor = conn.cursor()
    if level:
        cursor.execute(
            'SELECT COUNT(*) as count FROM logs WHERE user_id = ? AND level = ?',
            (user_id, level)
        )
    else:
        cursor.execute(
            'SELECT COUNT(*) as count FROM logs WHERE user_id = ?',
            (user_id,)
        )
    count = cursor.fetchone()['count']
    conn.close()
    return count

# ============ 设置管理 ============

def get_setting(user_id, key):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT value FROM settings WHERE user_id = ? AND key = ?',
        (user_id, key)
    )
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else None

def set_setting(user_id, key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?)
           ON CONFLICT(user_id, key) DO UPDATE SET value = ?''',
        (user_id, key, value, value)
    )
    conn.commit()
    conn.close()

def get_global_setting(key):
    return get_setting(None, key)

def set_global_setting(key, value):
    set_setting(None, key, value)
