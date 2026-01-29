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
        cursor.execute('SELECT COUNT(*) FROM messages')
        total_messages = cursor.fetchone()[0]
        
        # Average messages per user
        cursor.execute('''
            SELECT user_id, COUNT(*) as count FROM messages
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
            FROM messages
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
            FROM messages
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
    
    def get_all_users(self) -> list:
        """Get all users with basic info"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.last_name, p.plan
            FROM users u
            LEFT JOIN plans p ON u.user_id = p.user_id
            ORDER BY u.created_at DESC
        ''')
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'plan': row[4] or 'Free'
            })
        
        conn.close()
        return users
    
    def get_user_details(self, user_id: int) -> dict:
        """Get detailed info about a specific user"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.last_name, u.created_at,
                   p.plan, p.expiration,
                   s.model, s.current_persona
            FROM users u
            LEFT JOIN plans p ON u.user_id = p.user_id
            LEFT JOIN settings s ON u.user_id = s.user_id
            WHERE u.user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        
        # Get message count
        cursor.execute('SELECT COUNT(*) FROM messages WHERE user_id = ?', (user_id,))
        message_count = cursor.fetchone()[0]
        
        # Get media count
        cursor.execute('SELECT COUNT(*) FROM media WHERE user_id = ?', (user_id,))
        media_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'user_id': result[0],
            'username': result[1],
            'first_name': result[2],
            'last_name': result[3],
            'created_at': result[4],
            'plan': result[5] or 'Free',
            'expiration': result[6],
            'model': result[7],
            'persona': result[8],
            'message_count': message_count,
            'media_count': media_count
        }
    
    def get_user_message_count(self, user_id: int) -> int:
        """Get message count for specific user"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM messages WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def get_plan_distribution(self) -> dict:
        """Get plan distribution"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT plan, COUNT(*) as count FROM plans
            GROUP BY plan
        ''')
        
        distribution = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return distribution
    
    def get_active_users(self, days: int = 7) -> int:
        """Get count of users active in last N days"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) FROM messages
            WHERE created_at >= ?
        ''', (cutoff,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
        """Get recent errors from error log"""
        error_file = self.data_dir / 'errors.json'
        
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
            bar = "█" * min(count // 10, 50)
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