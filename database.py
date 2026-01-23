import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

class DatabaseManager:
    def __init__(self, db_path: str = 'gena.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database with all tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
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
        
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                model TEXT DEFAULT 'gemini-2.5-flash',
                current_persona TEXT DEFAULT 'friend',
                system_instruction TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Usage table (rate limiting)
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
        
        # Message history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Safety settings table (global settings)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                settings JSON DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_user_id ON message_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_created ON message_history(created_at)')
        
        conn.commit()
        conn.close()
    
    def init_user(self, user_id: int):
        """Initialize a new user with default values."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create user
        cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        
        # Create plan
        cursor.execute('''
            INSERT OR IGNORE INTO plans (user_id, plan, expiration)
            VALUES (?, 'Free', NULL)
        ''', (user_id,))
        
        # Create settings
        cursor.execute('''
            INSERT OR IGNORE INTO settings (user_id, model, current_persona, system_instruction)
            VALUES (?, 'gemini-2.5-flash', 'friend', ?)
        ''', (user_id, ''))  # system_instruction will be set by app
        
        # Create usage
        cursor.execute('''
            INSERT OR IGNORE INTO usage (user_id, rate_limit_minute, rate_limit_count)
            VALUES (?, '', 0)
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_user_plan(self, user_id: int) -> str:
        """Get user's current plan."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT plan, expiration FROM plans WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            self.init_user(user_id)
            return 'Free'
        
        plan, expiration = result
        
        # Check if plan expired
        if expiration:
            exp_time = datetime.fromisoformat(expiration)
            if exp_time < datetime.now():
                self.set_user_plan(user_id, 'Free')
                return 'Free'
        
        return plan
    
    def set_user_plan(self, user_id: int, plan: str, expiration: Optional[str] = None):
        """Set user's plan."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE plans SET plan = ?, expiration = ?
            WHERE user_id = ?
        ''', (plan, expiration, user_id))
        
        conn.commit()
        conn.close()
    
    def get_settings(self, user_id: int) -> Dict:
        """Get user's settings."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT model, current_persona, system_instruction FROM settings WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            self.init_user(user_id)
            return {
                'model': 'gemini-2.5-flash',
                'current_persona': 'friend',
                'systemInstruction': ''
            }
        
        model, persona, instruction = result
        return {
            'model': model,
            'current_persona': persona,
            'systemInstruction': instruction
        }
    
    def update_settings(self, user_id: int, **kwargs):
        """Update user's settings."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Map kwargs keys to database columns
        update_map = {
            'model': 'model',
            'current_persona': 'current_persona',
            'systemInstruction': 'system_instruction'
        }
        
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in update_map:
                updates.append(f"{update_map[key]} = ?")
                values.append(value)
        
        if updates:
            values.append(user_id)
            query = f"UPDATE settings SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?"
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def add_to_history(self, user_id: int, user_message: str, bot_response: str):
        """Add a message pair to history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO message_history (user_id, user_message, bot_response)
            VALUES (?, ?, ?)
        ''', (user_id, user_message, bot_response))
        
        conn.commit()
        conn.close()
    
    def get_history(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Get user's message history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_message, bot_response, created_at FROM message_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        history = []
        for user_msg, bot_msg, timestamp in reversed(results):
            history.append({
                'timestamp': timestamp,
                'user': user_msg,
                'bot': bot_msg
            })
        
        return history
    
    def clear_history(self, user_id: int):
        """Clear user's message history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM message_history WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_usage(self, user_id: int) -> Dict:
        """Get user's usage stats."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT rate_limit_minute, rate_limit_count, image_limit_count, image_limit_reset
            FROM usage WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            self.init_user(user_id)
            return {
                'rateLimit': {'minute': '', 'count': 0},
                'imageLimit': {'count': 0, 'resetTime': ''}
            }
        
        rate_minute, rate_count, image_count, image_reset = result
        return {
            'rateLimit': {'minute': rate_minute, 'count': rate_count},
            'imageLimit': {'count': image_count, 'resetTime': image_reset or ''}
        }
    
    def update_usage(self, user_id: int, rate_minute: str = None, rate_count: int = None, 
                    image_count: int = None, image_reset: str = None):
        """Update user's usage stats."""
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
            query = f"UPDATE usage SET {', '.join(updates)} WHERE user_id = ?"
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def get_safety_settings(self) -> List[Dict]:
        """Get global safety settings."""
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
        """Update global safety settings."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        settings_json = json.dumps(settings)
        
        # Insert or update (ensure only one row)
        cursor.execute('''
            INSERT INTO safety_settings (id, settings) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET settings = excluded.settings, updated_at = CURRENT_TIMESTAMP
        ''', (settings_json,))
        
        conn.commit()
        conn.close()
    
    def migrate_from_json(self, json_dir: Path):
        """Migrate data from JSON files to database."""
        users_dir = json_dir / 'data' / 'users'
        
        # Check for migration marker file
        migration_marker = json_dir / '.migration_complete'
        if migration_marker.exists():
            return
        
        # Migrate safety settings if they exist
        safety_file = json_dir / 'data' / 'safety.json'
        if safety_file.exists():
            try:
                with open(safety_file, 'r') as f:
                    safety_settings = json.load(f)
                    self.set_safety_settings(safety_settings)
                    print(f"✅ Safety settings migrated to database")
            except Exception as e:
                print(f"⚠️ Could not migrate safety.json: {e}")
        
        # Check if users directory exists
        if not users_dir.exists():
            migration_marker.touch()
            return
        
        for user_dir in users_dir.iterdir():
            if not user_dir.is_dir():
                continue
            
            try:
                user_id = int(user_dir.name)
            except ValueError:
                continue
            
            print(f"Migrating user {user_id}...")
            
            # Initialize user
            self.init_user(user_id)
            
            # Migrate plan
            plan_file = user_dir / 'plan.json'
            if plan_file.exists():
                with open(plan_file, 'r') as f:
                    plan_data = json.load(f)
                    self.set_user_plan(user_id, plan_data.get('plan', 'Free'), 
                                     plan_data.get('expiration'))
            
            # Migrate settings
            settings_file = user_dir / 'settings.json'
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    self.update_settings(user_id, **settings)
            
            # Migrate history
            history_file = user_dir / 'history.json'
            if history_file.exists():
                with open(history_file, 'r') as f:
                    history = json.load(f)
                    for entry in history:
                        if isinstance(entry, dict) and 'user' in entry and 'bot' in entry:
                            self.add_to_history(user_id, entry['user'], entry['bot'])
            
            print(f"✅ User {user_id} migrated successfully")
        
        # Create migration marker to skip this on next restart
        migration_marker = json_dir / '.migration_complete'
        migration_marker.touch()
        print("✅ Migration complete! Old JSON files can be safely deleted.")
