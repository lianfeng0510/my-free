from app import app, db

# 创建数据库表结构
with app.app_context():
    print("开始创建数据库表结构...")
    db.create_all()
    print("数据库表结构创建完成！")
