#!/usr/bin/env python3
"""
Database backup and restore utilities for Robinhood Portfolio Analysis
"""

import os
import sys
import shutil
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config import settings


class DatabaseBackup:
    """Database backup and restore utilities"""

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

        # Database paths
        self.portfolio_db = Path(settings.database_url.replace("sqlite:///", ""))
        self.stockr_db = Path(settings.stockr_db_path)

    def create_backup(self, name: str = None) -> str:
        """Create a backup of all databases"""
        if name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"backup_{timestamp}"

        backup_path = self.backup_dir / name
        backup_path.mkdir(exist_ok=True)

        print(f"📦 Creating backup: {name}")

        # Backup portfolio database
        if self.portfolio_db.exists():
            portfolio_backup = backup_path / "portfolio.db"
            shutil.copy2(self.portfolio_db, portfolio_backup)
            print(f"✅ Portfolio database backed up: {portfolio_backup}")
        else:
            print("⚠️  Portfolio database not found, skipping")

        # Backup stockr database
        if self.stockr_db.exists():
            stockr_backup = backup_path / "stockr.db"
            shutil.copy2(self.stockr_db, stockr_backup)
            print(f"✅ Stockr database backed up: {stockr_backup}")
        else:
            print("⚠️  Stockr database not found, skipping")

        # Create backup metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "name": name,
            "portfolio_db_size": self.portfolio_db.stat().st_size if self.portfolio_db.exists() else 0,
            "stockr_db_size": self.stockr_db.stat().st_size if self.stockr_db.exists() else 0,
            "environment": settings.environment
        }

        metadata_file = backup_path / "metadata.json"
        import json
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"📋 Backup metadata saved: {metadata_file}")
        print(f"🎉 Backup completed: {backup_path}")

        return str(backup_path)

    def restore_backup(self, name: str, confirm: bool = False) -> bool:
        """Restore a backup"""
        backup_path = self.backup_dir / name

        if not backup_path.exists():
            print(f"❌ Backup not found: {name}")
            return False

        if not confirm:
            print(f"⚠️  This will overwrite existing databases. Use --confirm to proceed.")
            print(f"Backup location: {backup_path}")
            return False

        print(f"🔄 Restoring backup: {name}")

        # Restore portfolio database
        portfolio_backup = backup_path / "portfolio.db"
        if portfolio_backup.exists():
            shutil.copy2(portfolio_backup, self.portfolio_db)
            print(f"✅ Portfolio database restored: {self.portfolio_db}")
        else:
            print("⚠️  Portfolio database backup not found")

        # Restore stockr database
        stockr_backup = backup_path / "stockr.db"
        if stockr_backup.exists():
            shutil.copy2(stockr_backup, self.stockr_db)
            print(f"✅ Stockr database restored: {self.stockr_db}")
        else:
            print("⚠️  Stockr database backup not found")

        print("🎉 Restore completed")
        return True

    def list_backups(self):
        """List all available backups"""
        backups = []
        for item in self.backup_dir.iterdir():
            if item.is_dir():
                metadata_file = item / "metadata.json"
                if metadata_file.exists():
                    import json
                    try:
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                        backups.append(metadata)
                    except:
                        backups.append({"name": item.name, "error": "Invalid metadata"})

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        print("📦 Available backups:")
        for backup in backups:
            name = backup.get("name", "Unknown")
            timestamp = backup.get("timestamp", "Unknown")
            print(f"  • {name} ({timestamp})")

        return backups

    def cleanup_old_backups(self, keep_days: int = 30):
        """Remove backups older than specified days"""
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=keep_days)
        removed_count = 0

        print(f"🧹 Cleaning up backups older than {keep_days} days...")

        for item in self.backup_dir.iterdir():
            if item.is_dir():
                metadata_file = item / "metadata.json"
                if metadata_file.exists():
                    try:
                        import json
                        with open(metadata_file) as f:
                            metadata = json.load(f)

                        backup_date = datetime.fromisoformat(metadata.get("timestamp", ""))
                        if backup_date < cutoff_date:
                            shutil.rmtree(item)
                            removed_count += 1
                            print(f"🗑️  Removed old backup: {item.name}")
                    except Exception as e:
                        print(f"⚠️  Error processing {item.name}: {e}")

        print(f"✅ Cleanup completed. Removed {removed_count} old backups.")


def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description="Database backup and restore utilities")
    parser.add_argument("action", choices=["backup", "restore", "list", "cleanup"],
                       help="Action to perform")
    parser.add_argument("--name", help="Backup name (for backup/restore actions)")
    parser.add_argument("--confirm", action="store_true",
                       help="Confirm destructive operations")
    parser.add_argument("--keep-days", type=int, default=30,
                       help="Days to keep backups during cleanup")

    args = parser.parse_args()

    backup = DatabaseBackup()

    if args.action == "backup":
        backup.create_backup(args.name)
    elif args.action == "restore":
        success = backup.restore_backup(args.name, args.confirm)
        if not success and not args.confirm:
            print("Use --confirm to actually perform the restore")
    elif args.action == "list":
        backup.list_backups()
    elif args.action == "cleanup":
        backup.cleanup_old_backups(args.keep_days)


if __name__ == "__main__":
    main()
