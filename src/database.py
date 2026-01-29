"""
Gena - Database Manager
SQLite database operations for user data, settings, and history
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path


class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: str = 'data/database.db'):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Initialize database with all tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table with first_name and last_name
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Plans table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                plan TEXT DEFAULT 'Free',
                expiration TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Settings table with custom instruction
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                model TEXT DEFAULT 'gemini-2.5-flash',
                current_persona TEXT DEFAULT 'friend',
                system_instruction TEXT,
                custom_instruction TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Add first_name and last_name columns if they don't exist (for existing databases)
        try:
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'first_name' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
                print("✅ Added first_name column to existing database")
            if 'last_name' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
                print("✅ Added last_name column to existing database")
        except Exception as e:
            pass
        
        # Usage table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                rate_limit_minute TEXT,
                rate_limit_count INTEGER DEFAULT 0,
                image_limit_count INTEGER DEFAULT 0,
                image_limit_reset TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Separate messages table for each user
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                media_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (media_id) REFERENCES media(id)
            )
        ''')
        
        # Media reference table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                file_path TEXT,
                mime_type TEXT,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Safety settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                settings JSON DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_user ON media(user_id, created_at DESC)')
        
        conn.commit()
        conn.close()
    
    def init_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Initialize a new user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, username, first_name, last_name))
        
        cursor.execute('INSERT OR IGNORE INTO plans (user_id) VALUES (?)', (user_id,))
        cursor.execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (user_id,))
        cursor.execute('INSERT OR IGNORE INTO usage (user_id) VALUES (?)', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_user_info(self, user_id: int) -> Dict:
        """Get user information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT username, first_name, last_name FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'username': result[0], 
                'first_name': result[1],
                'last_name': result[2],
                'full_name': f"{result[1]} {result[2]}".strip() if result[1] or result[2] else None
            }
        return {'username': None, 'first_name': 'friend', 'last_name': None, 'full_name': 'friend'}
    
    def get_user_plan(self, user_id: int) -> str:
        """Get user's current plan"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT plan, expiration FROM plans WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return 'Free'
        
        plan, expiration = result
        
        if expiration:
            exp_time = datetime.fromisoformat(expiration)
            if exp_time < datetime.now():
                self.set_user_plan(user_id, 'Free')
                return 'Free'
        
        return plan
    
    def set_user_plan(self, user_id: int, plan: str, expiration: Optional[str] = None):
        """Set user's plan"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE plans SET plan = ?, expiration = ? WHERE user_id = ?', 
                      (plan, expiration, user_id))
        
        conn.commit()
        conn.close()
    
    def get_plan_expiration(self, user_id: int) -> Optional[str]:
        """Get plan expiration"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT expiration FROM plans WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_settings(self, user_id: int) -> Dict:
        """Get user settings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT model, current_persona, system_instruction, custom_instruction 
            FROM settings WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return {
                'model': 'gemini-2.5-flash',
                'current_persona': 'friend',
                'systemInstruction': '',
                'customInstruction': ''
            }
        
        return {
            'model': result[0],
            'current_persona': result[1],
            'systemInstruction': result[2] or '',
            'customInstruction': result[3] or ''
        }
    
    def update_settings(self, user_id: int, **kwargs):
        """Update user settings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        update_map = {
            'model': 'model',
            'current_persona': 'current_persona',
            'systemInstruction': 'system_instruction',
            'customInstruction': 'custom_instruction'
        }
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in update_map:
                updates.append(f"{update_map[key]} = ?")
                values.append(value)
        
        if updates:
            values.append(user_id)
            query = f'UPDATE settings SET {", ".join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?'
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def add_message(self, user_id: int, role: str, content: str, media_id: int = None):
        """Add a message to history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO messages (user_id, role, content, media_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, role, content, media_id))
        
        conn.commit()
        conn.close()
    
    def add_media(self, user_id: int, file_id: str, file_path: str, mime_type: str, file_size: int) -> int:
        """Add media reference and return media_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO media (user_id, file_id, file_path, mime_type, file_size)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, file_id, file_path, mime_type, file_size))
        
        media_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return media_id
    
    def get_history(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Get conversation history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT m.id, m.role, m.content, m.created_at, m.media_id, med.file_path, med.mime_type
            FROM messages m
            LEFT JOIN media med ON m.media_id = med.id
            WHERE m.user_id = ?
            ORDER BY m.created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        history = []
        for msg_id, role, content, timestamp, media_id, file_path, mime_type in reversed(results):
            entry = {
                'id': msg_id,
                'role': role,
                'content': content,
                'timestamp': timestamp
            }
            if media_id and file_path:
                entry['type'] = 'media'
                entry['media_ref'] = media_id
                entry['file_path'] = file_path
                entry['mime_type'] = mime_type
            else:
                entry['type'] = 'text'
            
            history.append(entry)
        
        return history
    
    def clear_history(self, user_id: int):
        """Clear user messages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_usage(self, user_id: int) -> Dict:
        """Get usage stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT rate_limit_minute, rate_limit_count, image_limit_count, image_limit_reset
            FROM usage WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return {
                'rateLimit': {'minute': '', 'count': 0},
                'imageLimit': {'count': 0, 'resetTime': ''}
            }
        
        return {
            'rateLimit': {'minute': result[0], 'count': result[1]},
            'imageLimit': {'count': result[2], 'resetTime': result[3] or ''}
        }
    
    def update_usage(self, user_id: int, rate_minute: str = None, rate_count: int = None, 
                    image_count: int = None, image_reset: str = None):
        """Update usage stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        if rate_minute is not None:
            updates.append('rate_limit_minute = ?')
            values.append(rate_minute)
        if rate_count is not None:
            updates.append('rate_limit_count = ?')
            values.append(rate_count)
        if image_count is not None:
            updates.append('image_limit_count = ?')
            values.append(image_count)
        if image_reset is not None:
            updates.append('image_limit_reset = ?')
            values.append(image_reset)
        
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.append(user_id)
            query = f'UPDATE usage SET {", ".join(updates)} WHERE user_id = ?'
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def get_safety_settings(self) -> List[Dict]:
        """Get safety settings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT settings FROM safety_settings WHERE id = 1')
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            return []
        
        try:
            return json.loads(result[0])
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_safety_settings(self, settings: List[Dict]):
        """Set safety settings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        settings_json = json.dumps(settings)
        
        cursor.execute('''
            INSERT INTO safety_settings (id, settings) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET settings = excluded.settings, updated_at = CURRENT_TIMESTAMP
        ''', (settings_json,))
        
        conn.commit()
        conn.close()
    
    def get_total_users(self) -> int:
        """Get total user count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_total_messages(self) -> int:
        """Get total message count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM messages')
        count = cursor.fetchone()[0]
        conn.close()
        return count