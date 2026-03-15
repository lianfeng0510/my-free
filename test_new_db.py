from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

# 创建一个全新的Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'  # 使用新的数据库文件
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库和密码哈希工具
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# 重新定义User模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)  # 明确使用password_hash字段

    # 添加密码设置和验证方法
    def set_password(self, password):
        """设置密码哈希"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """验证密码"""
        return bcrypt.check_password_hash(self.password_hash, password)

# 测试函数
def test_new_db():
    print("开始测试全新数据库...")
    
    # 删除旧的测试文件
    import os
    if os.path.exists('test.db'):
        os.remove('test.db')
        print("删除旧的测试数据库文件")
    
    # 创建应用上下文
    with app.app_context():
        # 创建数据库表结构
        print("创建数据库表结构...")
        db.create_all()
        print("数据库表结构创建完成")
        
        # 测试创建用户
        print("\n测试创建用户")
        user = User(username="testuser")
        user.set_password("password123")
        print(f"用户创建成功，密码哈希: {user.password_hash}")
        
        # 保存到数据库
        print("\n测试保存到数据库")
        db.session.add(user)
        db.session.commit()
        print("用户保存成功")
        
        # 从数据库加载
        print("\n测试从数据库加载")
        loaded_user = User.query.filter_by(username="testuser").first()
        if loaded_user:
            print(f"用户加载成功，用户名: {loaded_user.username}")
            print(f"密码哈希: {loaded_user.password_hash}")
        else:
            print("用户加载失败")
        
        # 测试密码验证
        print("\n测试密码验证")
        if loaded_user:
            print(f"验证正确密码: {loaded_user.check_password('password123')}")
            print(f"验证错误密码: {loaded_user.check_password('wrongpass')}")
        
        print("\n测试完成！")

if __name__ == "__main__":
    test_new_db()
