"""
Admin dashboard and analytics for Gena bot
"""
from database import DatabaseManager
from datetime import datetime, timedelta
from pathlib import Path
import json
import sqlite3


class AdminDashboard:
    """Admin dashboard for monitoring bot usage and analytics"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.data_dir = Path.cwd() / 'data'
    
    def get_user_stats(self) -> dict:
        """Get statistics about bot users"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Total users
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Plan distribution
        cursor.execute('''
            SELECT plan, COUNT(*) as count FROM plans
            GROUP BY plan
        ''')
        plan_distribution = dict(cursor.fetchall())
        
        # Total messages
        cursor.execute('SELECT COUNT(*) FROM message_history')
        total_messages = cursor.fetchone()[0]
        
        # Average messages per user
        cursor.execute('''
            SELECT user_id, COUNT(*) as count FROM message_history
            GROUP BY user_id
        ''')
        message_counts = [row[1] for row in cursor.fetchall()]
        avg_messages = sum(message_counts) / len(message_counts) if message_counts else 0
        
        conn.close()
        
        return {
            'total_users': total_users,
            'plan_distribution': plan_distribution,
            'total_messages': total_messages,
            'avg_messages_per_user': round(avg_messages, 2)
        }
    
    def get_popular_personas(self) -> dict:
        """Get which personas are most popular"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT current_persona, COUNT(*) as count FROM settings
            GROUP BY current_persona
            ORDER BY count DESC
        ''')
        
        personas = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return personas
    
    def get_daily_activity(self, days: int = 7) -> dict:
        """Get daily message activity for the last N days"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).date()
        
        cursor.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM message_history
            WHERE DATE(created_at) >= ?
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (str(start_date),))
        
        activity = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return activity
    
    def get_top_users(self, limit: int = 10) -> list:
        """Get most active users"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, COUNT(*) as message_count
            FROM message_history
            GROUP BY user_id
            ORDER BY message_count DESC
            LIMIT ?
        ''', (limit,))
        
        top_users = [
            {'user_id': row[0], 'messages': row[1]}
            for row in cursor.fetchall()
        ]
        conn.close()
        
        return top_users
    
    def get_error_log(self) -> list:
        """Get recent errors from error log"""
        error_file = self.data_dir / 'errors' / 'errors.json'
        
        if not error_file.exists():
            return []
        
        try:
            with open(error_file, 'r') as f:
                errors = json.load(f)
                return errors[-50:] if isinstance(errors, list) else []
        except:
            return []
    
    def generate_report(self) -> str:
        """Generate a full admin report"""
        stats = self.get_user_stats()
        personas = self.get_popular_personas()
        activity = self.get_daily_activity(7)
        top_users = self.get_top_users(5)
        
        report = f"""
╔════════════════════════════════════════╗
║        GENA BOT - ADMIN REPORT         ║
║        {datetime.now().strftime('%Y-%m-%d %H:%M')}                 ║
╚════════════════════════════════════════╝

📊 USER STATISTICS
├── Total Users: {stats['total_users']}
├── Plan Distribution:
│   ├── Free: {stats['plan_distribution'].get('Free', 0)}
│   ├── Basic: {stats['plan_distribution'].get('Basic', 0)}
│   ├── Premium: {stats['plan_distribution'].get('Premium', 0)}
│   └── VIP: {stats['plan_distribution'].get('VIP', 0)}
├── Total Messages: {stats['total_messages']}
└── Avg Messages/User: {stats['avg_messages_per_user']}

👤 TOP PERSONAS
"""
        for idx, (persona, count) in enumerate(
            sorted(personas.items(), key=lambda x: x[1], reverse=True)[:5], 
            1
        ):
            report += f"├── {idx}. {persona}: {count} users\n"
        
        report += "\n📈 7-DAY ACTIVITY\n"
        for date, count in sorted(activity.items())[-7:]:
            bar = "█" * min(count // 10, 50)  # Max 50 chars
            report += f"├── {date}: {bar} ({count} msgs)\n"
        
        report += "\n🏆 TOP 5 USERS\n"
        for idx, user in enumerate(top_users, 1):
            report += f"├── {idx}. User {user['user_id']}: {user['messages']} messages\n"
        
        return report
    
    def export_analytics(self, filepath: str) -> bool:
        """Export analytics to JSON file"""
        try:
            analytics = {
                'timestamp': datetime.now().isoformat(),
                'user_stats': self.get_user_stats(),
                'popular_personas': self.get_popular_personas(),
                'daily_activity': self.get_daily_activity(30),
                'top_users': self.get_top_users(20)
            }
            
            with open(filepath, 'w') as f:
                json.dump(analytics, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Failed to export analytics: {e}")
            return False