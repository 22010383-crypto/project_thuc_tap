"""
Database Migration Script
========================
Migrate from v1.0 to v2.0 schema (add liveness columns).
"""

import sqlite3
import os
import shutil
from datetime import datetime
from app.config import Config

def backup_database():
    """Backup current database."""
    if not os.path.exists(Config.DB_PATH):
        print("⚠️  No existing database found. Will create new one.")
        return None
    
    backup_path = Config.DB_PATH + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(Config.DB_PATH, backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    return backup_path

def check_columns_exist(conn):
    """Check if new columns already exist."""
    cursor = conn.execute("PRAGMA table_info(attendance_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_columns = ['confidence_score', 'liveness_score', 'liveness_passed', 'liveness_details']
    existing = [col for col in new_columns if col in columns]
    missing = [col for col in new_columns if col not in columns]
    
    return existing, missing

def migrate_database():
    """Migrate database to v2.0 schema."""
    print("=" * 60)
    print("Database Migration: v1.0 → v2.0")
    print("=" * 60)
    
    # Backup first
    backup_path = backup_database()
    
    # Connect to database
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check existing columns
        existing, missing = check_columns_exist(conn)
        
        if existing:
            print(f"✅ Found existing columns: {existing}")
        
        if not missing:
            print("✅ Database already up to date!")
            conn.close()
            return True
        
        print(f"📝 Adding missing columns: {missing}")
        
        # Add columns one by one
        if 'confidence_score' in missing:
            cursor.execute("""
                ALTER TABLE attendance_logs 
                ADD COLUMN confidence_score REAL
            """)
            print("  ✓ Added confidence_score")
        
        if 'liveness_score' in missing:
            cursor.execute("""
                ALTER TABLE attendance_logs 
                ADD COLUMN liveness_score REAL DEFAULT 0.0
            """)
            print("  ✓ Added liveness_score")
        
        if 'liveness_passed' in missing:
            cursor.execute("""
                ALTER TABLE attendance_logs 
                ADD COLUMN liveness_passed BOOLEAN DEFAULT 1
            """)
            print("  ✓ Added liveness_passed")
        
        if 'liveness_details' in missing:
            cursor.execute("""
                ALTER TABLE attendance_logs 
                ADD COLUMN liveness_details TEXT
            """)
            print("  ✓ Added liveness_details")
        
        # Create indexes if not exist
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_time 
            ON attendance_logs(checkin_time)
        """)
        print("  ✓ Created index on checkin_time")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        # Verify
        existing, missing = check_columns_exist(conn)
        print(f"\n📊 Final schema: {len(existing)} new columns added")
        
        conn.close()
        return True
    
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.close()
        
        # Restore from backup
        if backup_path and os.path.exists(backup_path):
            print(f"🔄 Restoring from backup: {backup_path}")
            shutil.copy2(backup_path, Config.DB_PATH)
            print("✅ Database restored")
        
        return False

def main():
    """Main entry point."""
    print("\n⚠️  This script will modify your database.")
    print("A backup will be created automatically.")
    
    response = input("\nContinue? (y/n): ").strip().lower()
    
    if response != 'y':
        print("❌ Migration cancelled")
        return
    
    success = migrate_database()
    
    if success:
        print("\n" + "=" * 60)
        print("Migration completed! You can now run the application.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Migration failed. Please check the error above.")
        print("=" * 60)

if __name__ == "__main__":
    main()
