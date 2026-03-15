from app import app, db, User, bcrypt

# 测试密码哈希功能
def test_password_hash():
    print("开始测试密码哈希功能...")
    
    # 创建应用上下文
    with app.app_context():
        # 创建数据库表结构
        print("创建数据库表结构...")
        db.create_all()
        
        # 测试1: 创建用户并设置密码
        print("测试1: 创建用户并设置密码")
        user = User(username="testuser")
        user.set_password("password123")
        
        # 验证密码哈希是否生成
        print(f"密码哈希生成: {user.password_hash}")
        print(f"密码哈希长度: {len(user.password_hash)}")
        assert len(user.password_hash) == 60, f"密码哈希长度应该是60，实际是{len(user.password_hash)}"
        assert user.password_hash.startswith('$2b$'), "密码哈希应该以$2b$开头（bcrypt格式）"
        
        # 测试2: 验证密码
        print("\n测试2: 验证密码")
        assert user.check_password("password123"), "正确密码应该验证通过"
        assert not user.check_password("wrongpassword"), "错误密码应该验证失败"
        print("密码验证测试通过")
        
        # 测试3: 保存到数据库并从数据库加载
        print("\n测试3: 保存到数据库并从数据库加载")
        db.session.add(user)
        db.session.commit()
        
        # 从数据库加载用户
        loaded_user = User.query.filter_by(username="testuser").first()
        assert loaded_user is not None, "应该能从数据库加载用户"
        assert loaded_user.password_hash == user.password_hash, "加载的用户密码哈希应该与原始相同"
        assert loaded_user.check_password("password123"), "加载的用户应该能验证正确密码"
        print("数据库存储测试通过")
        
        # 测试4: 测试用户唯一性
        print("\n测试4: 测试用户唯一性")
        duplicate_user = User(username="testuser")
        duplicate_user.set_password("password456")
        try:
            db.session.add(duplicate_user)
            db.session.commit()
            assert False, "应该抛出用户名重复异常"
        except Exception as e:
            db.session.rollback()
            print(f"正确捕获到用户名重复异常: {e}")
        
        print("\n所有测试通过！密码哈希功能正常工作。")

if __name__ == "__main__":
    test_password_hash()
