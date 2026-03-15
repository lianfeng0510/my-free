def allowed_file(filename, allowed_extensions):
    """检查文件扩展名是否在允许的列表中"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
