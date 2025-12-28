#!/usr/bin/env python3
"""Test script for POP3 + PostgreSQL integration."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.pop3_service import (
    Pop3Config,
    DatabaseConfig,
    DatabaseService,
    Pop3EmailService,
)


async def test_database():
    """Test database connection and schema creation."""
    print("\n🔍 Testing Database Connection...\n")
    
    config = DatabaseConfig(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        database=os.getenv("DATABASE_NAME", "mindops_entegrasyon"),
        user=os.getenv("DATABASE_USER", "aria"),
        password=os.getenv("DATABASE_PASSWORD", "aria_secure_2024"),
    )
    
    db = DatabaseService(config)
    
    try:
        await db.connect()
        print("   ✅ Database connected!")
        
        await db.initialize_schema()
        print("   ✅ Schema initialized!")
        
        # Test stats
        stats = await db.get_stats()
        print(f"   📊 Stats: {stats}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False
        
    finally:
        await db.disconnect()


async def test_pop3():
    """Test POP3 connection."""
    print("\n📧 Testing POP3 Connection...\n")
    
    # Test booking email
    print("1️⃣ Booking Email:")
    try:
        config = Pop3Config(
            host=os.getenv("BOOKING_POP3_HOST", "mail.pointholiday.com"),
            port=int(os.getenv("BOOKING_POP3_PORT", "995")),
            username=os.getenv("BOOKING_POP3_ADDRESS", "booking@pointholiday.com"),
            password=os.getenv("BOOKING_POP3_PASSWORD", ""),
        )
        
        import ssl
        import poplib
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        server = poplib.POP3_SSL(
            config.host,
            config.port,
            context=context,
            timeout=30,
        )
        
        server.user(config.username)
        server.pass_(config.password)
        
        num_messages = len(server.list()[1])
        print(f"   ✅ Connected! {num_messages} messages in mailbox")
        
        server.quit()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test stopsale email
    print("\n2️⃣ Stop Sale Email:")
    try:
        config = Pop3Config(
            host=os.getenv("STOPSALE_POP3_HOST", "mail.pointholiday.com"),
            port=int(os.getenv("STOPSALE_POP3_PORT", "995")),
            username=os.getenv("STOPSALE_POP3_ADDRESS", "stopsale@pointholiday.com"),
            password=os.getenv("STOPSALE_POP3_PASSWORD", ""),
        )
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        server = poplib.POP3_SSL(
            config.host,
            config.port,
            context=context,
            timeout=30,
        )
        
        server.user(config.username)
        server.pass_(config.password)
        
        num_messages = len(server.list()[1])
        print(f"   ✅ Connected! {num_messages} messages in mailbox")
        
        server.quit()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def main():
    """Run all tests."""
    # Load env
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    
    print("\n" + "=" * 50)
    print("🧪 MindOpsOS Entegrasyon - POP3 + PostgreSQL Test")
    print("=" * 50)
    
    # Test database
    db_ok = await test_database()
    
    # Test POP3
    await test_pop3()
    
    print("\n" + "=" * 50)
    print("✅ Tests Complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
