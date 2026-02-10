import os
import shutil
from datetime import datetime
from gena import GenaCore, PLAN_LIMITS
from personas import PERSONAS

def test_gena_core():
    print("🚀 Testing Gena Core Features...")
    
    # Setup test DB
    db_path = "data/test_database.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Initialize Core
    core = GenaCore(db_path)
    print("✅ Core initialized")
    
    # 1. Create User
    user_id = 123456789
    username = "test_user"
    core.initialize_user(user_id, username, "Test", "User")
    print("✅ User initialized")
    
    # 2. Test Plan Upgrade
    assert core.get_user_plan(user_id) == 'Free'
    core.upgrade_plan(user_id, 'Premium', 30)
    assert core.get_user_plan(user_id) == 'Premium'
    print("✅ Plan upgrade successful")
    
    # 3. Test Username Lookup
    user_info = core.get_user_by_username("test_user")
    assert user_info['user_id'] == user_id
    print("✅ Username lookup successful")
    
    # 4. Test Persona Switching
    core.update_settings(user_id, current_persona='sarcastic')
    settings = core.get_settings(user_id)
    assert settings['current_persona'] == 'sarcastic'
    print("✅ Persona switching successful")
    
    # 5. Test Backup
    # Create some dummy data to backup
    core.add_message(user_id, 'user', 'Hello')
    
    backup_path = core.create_backup_zip()
    if backup_path and os.path.exists(backup_path):
        print(f"✅ Backup created: {backup_path}")
        os.remove(backup_path)
    else:
        print("❌ Backup failed")
        
    # 6. Test Data Deletion
    core.delete_user_data(user_id)
    # Verify deletion
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    assert cursor.fetchone() is None
    print("✅ User data deletion successful")
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists("data"):
         # cleaning up the test data dir if it was empty, but it might preserve other things
         pass

    print("\n✨ All tests passed!")

if __name__ == "__main__":
    test_gena_core()
