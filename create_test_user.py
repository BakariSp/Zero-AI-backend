import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import bcrypt  # 直接使用 bcrypt 而不是通过 passlib

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import User, Base
from app.db import SessionLocal

def create_test_user(email, username, password, is_superuser=False):
    db = SessionLocal()
    
    try:
        # 检查用户是否已存在 - 使用更具体的查询，只选择必要的列
        existing_user = db.query(User.id).filter(User.email == email).first()
        if existing_user:
            print(f"user {email} already exists")
            return
        
        # 创建新用户 - 使用 bcrypt 直接哈希密码
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
        
        new_user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=is_superuser,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_user)
        db.commit()
        print(f"user {email} created")
    except Exception as e:
        db.rollback()
        print(f"create user {email} error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user("admin@example.com", "admin", "admin123", is_superuser=True)
    create_test_user("test@example.com", "testuser", "password123")