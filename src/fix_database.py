"""
Fix Database - Complete migration and upgrade tool
Run this to migrate from old versions and fix schema issues
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime


def fix_database():
    """Complete database fix and migration"""
    
    db_path = Path('data/database.db')
    
    print("🔧 Starting database migration and fixes...\n")
    
    if not db_path.exists():
        print("ℹ️  No existing database found - will be created on first run")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Check and add missing columns to settings
        print("1️⃣  Checking settings table...")
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'custom_instruction' not in columns:
            cursor.execute("ALTER TABLE settings ADD COLUMN custom_instruction TEXT DEFAULT ''")
            print("   ✅ Added custom_instruction column")
        else:
            print("   ✅ custom_instruction column exists")
        
        conn.commit()
        
        # 2. Check and add username/first_name/last_name to users
        print("\n2️⃣  Checking users table...")
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in cursor.fetchall()]
        
        if 'username' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
            print("   ✅ Added username column")
        else:
            print("   ✅ username column exists")
        
        if 'first_name' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
            print("   ✅ Added first_name column")
        else:
            print("   ✅ first_name column exists")
        
        if 'last_name' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
            print("   ✅ Added last_name column")
        else:
            print("   ✅ last_name column exists")
        
        # Remove old full_name if it exists and migrate data
        if 'full_name' in user_columns:
            print("   🔄 Migrating full_name to first_name/last_name...")
            cursor.execute('SELECT user_id, full_name FROM users WHERE full_name IS NOT NULL')
            for user_id, full_name in cursor.fetchall():
                parts = full_name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''
                cursor.execute(
                    'UPDATE users SET first_name = ?, last_name = ? WHERE user_id = ?',
                    (first_name, last_name, user_id)
                )
            print("   ✅ Migrated full_name data")
        
        conn.commit()
        
        # 3. Check if we need to migrate from message_history to messages
        print("\n3️⃣  Checking message tables...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'message_history' in tables and 'messages' not in tables:
            print("   ⚠️  Old message_history table found - migrating...")
            
            # Create new messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    media_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Migrate old data - THIS IS THE FIX!
            cursor.execute('SELECT user_id, user_message, bot_response, created_at FROM message_history ORDER BY id')
            old_messages = cursor.fetchall()
            
            migrated_count = 0
            for user_id, user_msg, bot_msg, timestamp in old_messages:
                # Insert user message
                cursor.execute(
                    'INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)',
                    (user_id, 'user', user_msg, timestamp)
                )
                # Insert bot response
                cursor.execute(
                    'INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)',
                    (user_id, 'assistant', bot_msg, timestamp)
                )
                migrated_count += 1
            
            conn.commit()
            
            # Rename old table as backup
            cursor.execute('ALTER TABLE message_history RENAME TO message_history_backup')
            conn.commit()
            
            print(f"   ✅ Migrated {migrated_count} message pairs ({migrated_count * 2} total messages)")
            print("   ℹ️  Old table renamed to message_history_backup")
        
        elif 'messages' in tables:
            # Count messages
            cursor.execute('SELECT COUNT(*) FROM messages')
            msg_count = cursor.fetchone()[0]
            print(f"   ✅ Messages table exists with {msg_count} messages")
        else:
            print("   ℹ️  No message tables yet - will be created on first use")
        
        conn.commit()
        
        # 4. Create media table if it doesn't exist
        print("\n4️⃣  Checking media table...")
        if 'media' not in tables:
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
            print("   ✅ Created media table")
        else:
            cursor.execute('SELECT COUNT(*) FROM media')
            media_count = cursor.fetchone()[0]
            print(f"   ✅ Media table exists with {media_count} files")
        
        conn.commit()
        
        # 5. Create indexes if they don't exist
        print("\n5️⃣  Creating indexes...")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_user 
            ON messages(user_id, created_at DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_media_user 
            ON media(user_id, created_at DESC)
        ''')
        print("   ✅ Indexes created")
        
        conn.commit()
        
        # 6. Migrate from old JSON files if they exist
        print("\n6️⃣  Checking for old JSON data...")
        users_dir = Path('data/users')
        
        if users_dir.exists():
            print("   📦 Found old user data - migrating...")
            migrated = 0
            
            for user_dir in users_dir.iterdir():
                if not user_dir.is_dir():
                    continue
                
                try:
                    user_id = int(user_dir.name)
                except ValueError:
                    continue
                
                # Check if user already exists
                cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
                if cursor.fetchone():
                    print(f"   ⏭️  User {user_id} already migrated, skipping...")
                    continue
                
                # Insert user
                cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
                
                # Migrate plan
                plan_file = user_dir / 'plan.json'
                if plan_file.exists():
                    with open(plan_file, 'r') as f:
                        plan_data = json.load(f)
                        cursor.execute('''
                            INSERT OR IGNORE INTO plans (user_id, plan, expiration)
                            VALUES (?, ?, ?)
                        ''', (user_id, plan_data.get('plan', 'Free'), plan_data.get('expiration')))
                
                # Migrate settings
                settings_file = user_dir / 'settings.json'
                if settings_file.exists():
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                        cursor.execute('''
                            INSERT OR IGNORE INTO settings 
                            (user_id, model, current_persona, system_instruction, custom_instruction)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            user_id,
                            settings.get('model', 'gemini-2.5-flash'),
                            settings.get('current_persona', 'buddy'),
                            settings.get('systemInstruction', ''),
                            settings.get('customInstruction', '')
                        ))
                
                # Migrate usage
                usage_file = user_dir / 'usage.json'
                if usage_file.exists():
                    with open(usage_file, 'r') as f:
                        usage = json.load(f)
                        rate_limit = usage.get('rateLimit', {})
                        image_limit = usage.get('imageLimit', {})
                        
                        cursor.execute('''
                            INSERT OR IGNORE INTO usage 
                            (user_id, rate_limit_minute, rate_limit_count, 
                             image_limit_count, image_limit_reset)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            user_id,
                            rate_limit.get('minute', ''),
                            rate_limit.get('count', 0),
                            image_limit.get('count', 0),
                            image_limit.get('resetTime', '')
                        ))
                
                # Migrate history - FIXED: Properly insert messages
                history_file = user_dir / 'history.json'
                if history_file.exists():
                    with open(history_file, 'r') as f:
                        history = json.load(f)
                        msg_count = 0
                        for entry in history:
                            if isinstance(entry, dict) and 'user' in entry and 'bot' in entry:
                                timestamp = entry.get('timestamp', datetime.now().isoformat())
                                # User message
                                cursor.execute('''
                                    INSERT INTO messages (user_id, role, content, created_at)
                                    VALUES (?, ?, ?, ?)
                                ''', (user_id, 'user', entry['user'], timestamp))
                                # Bot response
                                cursor.execute('''
                                    INSERT INTO messages (user_id, role, content, created_at)
                                    VALUES (?, ?, ?, ?)
                                ''', (user_id, 'assistant', entry['bot'], timestamp))
                                msg_count += 1
                        print(f"      ✅ Migrated {msg_count} message pairs for user {user_id}")
                
                migrated += 1
                conn.commit()
            
            if migrated > 0:
                print(f"   ✅ Migrated {migrated} users from JSON files")
                print(f"   ℹ️  You can now safely delete the 'data/users' directory")
            else:
                print("   ℹ️  All users already migrated")
        else:
            print("   ℹ️  No old JSON data found")
        
        # 7. Migrate global safety settings
        print("\n7️⃣  Checking safety settings...")
        safety_file = Path('data/safety.json')
        if safety_file.exists():
            cursor.execute('SELECT id FROM safety_settings WHERE id = 1')
            if not cursor.fetchone():
                with open(safety_file, 'r') as f:
                    safety_data = json.load(f)
                    cursor.execute('''
                        INSERT INTO safety_settings (id, settings)
                        VALUES (1, ?)
                    ''', (json.dumps(safety_data),))
                print("   ✅ Migrated safety settings")
            else:
                print("   ✅ Safety settings already exist")
        else:
            print("   ℹ️  No old safety settings found")
        
        conn.commit()
        
        # Summary
        print("\n" + "="*60)
        print("✅ Database migration and fixes complete!")
        print("="*60)
        
        # Show statistics
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM messages')
        msg_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM media')
        media_count = cursor.fetchone()[0]
        
        print(f"\n📊 Database Statistics:")
        print(f"   👥 Users: {user_count}")
        print(f"   💬 Messages: {msg_count}")
        print(f"   🖼️  Media Files: {media_count}")
        
        # Check if message_history_backup exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message_history_backup'")
        if cursor.fetchone():
            print(f"\n💡 Backup Table Info:")
            print(f"   📦 message_history_backup exists (safe to delete after verification)")
        
        if users_dir.exists():
            print(f"\n💡 Next Steps:")
            print(f"   1. Test the bot to make sure everything works")
            print(f"   2. Check that your messages are visible")
            print(f"   3. Once confirmed, you can delete:")
            print(f"      - data/users/ (entire directory)")
            print(f"      - data/safety.json")
        
        print("\n🎉 You're all set! Run the bot now.")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    fix_database()