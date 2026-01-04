import os
import shutil
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = '/pjdata'

def get_user_path(username):
    """获取用户项目目录"""
    return os.path.join(PROJECT_ROOT, username)

def get_project_path(username, project_id):
    """获取项目目录"""
    return os.path.join(PROJECT_ROOT, username, project_id)

def ensure_user_dir(username):
    """确保用户目录存在"""
    user_path = get_user_path(username)
    os.makedirs(user_path, exist_ok=True)
    return user_path

def create_project_dir(username, project_id):
    """创建项目目录"""
    project_path = get_project_path(username, project_id)
    os.makedirs(project_path, exist_ok=True)
    return project_path

def delete_project_dir(username, project_id):
    """删除项目目录"""
    project_path = get_project_path(username, project_id)
    if os.path.exists(project_path):
        shutil.rmtree(project_path)
        return True
    return False

def list_files(username, project_id, subpath=''):
    """列出目录下的文件"""
    project_path = get_project_path(username, project_id)
    full_path = os.path.join(project_path, subpath) if subpath else project_path
    
    # 安全检查：确保路径在项目目录内
    full_path = os.path.abspath(full_path)
    if not full_path.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    if not os.path.exists(full_path):
        return []
    
    files = []
    for item in os.listdir(full_path):
        item_path = os.path.join(full_path, item)
        try:
            stat = os.stat(item_path)
            is_dir = os.path.isdir(item_path)
            files.append({
                'name': item,
                'type': 'folder' if is_dir else 'file',
                'size': format_size(stat.st_size) if not is_dir else '-',
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'raw_size': stat.st_size,
                'raw_modified': stat.st_mtime
            })
        except OSError:
            continue
    
    # 文件夹在前，文件在后，按名称排序
    files.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))
    return files

def format_size(size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f'{size:.1f} {unit}' if unit != 'B' else f'{size} {unit}'
        size /= 1024
    return f'{size:.1f} TB'

def read_file(username, project_id, filepath):
    """读取文件内容"""
    project_path = get_project_path(username, project_id)
    full_path = os.path.join(project_path, filepath)
    
    # 安全检查
    full_path = os.path.abspath(full_path)
    if not full_path.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    if not os.path.isfile(full_path):
        raise FileNotFoundError('File not found')
    
    # 检查文件大小，限制 5MB
    if os.path.getsize(full_path) > 5 * 1024 * 1024:
        raise ValueError('File too large')
    
    with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def write_file(username, project_id, filepath, content):
    """写入文件内容"""
    project_path = get_project_path(username, project_id)
    full_path = os.path.join(project_path, filepath)
    
    # 安全检查
    full_path = os.path.abspath(full_path)
    if not full_path.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    # 确保父目录存在
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_folder(username, project_id, folderpath):
    """创建文件夹"""
    project_path = get_project_path(username, project_id)
    full_path = os.path.join(project_path, folderpath)
    
    # 安全检查
    full_path = os.path.abspath(full_path)
    if not full_path.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    os.makedirs(full_path, exist_ok=True)

def delete_item(username, project_id, itempath):
    """删除文件或文件夹"""
    project_path = get_project_path(username, project_id)
    full_path = os.path.join(project_path, itempath)
    
    # 安全检查
    full_path = os.path.abspath(full_path)
    if not full_path.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    # 不允许删除项目根目录
    if full_path == os.path.abspath(project_path):
        raise PermissionError('Cannot delete project root')
    
    if os.path.isdir(full_path):
        shutil.rmtree(full_path)
    elif os.path.isfile(full_path):
        os.remove(full_path)
    else:
        raise FileNotFoundError('Item not found')

def rename_item(username, project_id, oldpath, newname):
    """重命名文件或文件夹"""
    project_path = get_project_path(username, project_id)
    old_full = os.path.join(project_path, oldpath)
    new_full = os.path.join(os.path.dirname(old_full), newname)
    
    # 安全检查
    old_full = os.path.abspath(old_full)
    new_full = os.path.abspath(new_full)
    if not old_full.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    if not new_full.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    os.rename(old_full, new_full)

def save_upload(username, project_id, subpath, file):
    """保存上传的文件"""
    project_path = get_project_path(username, project_id)
    target_dir = os.path.join(project_path, subpath) if subpath else project_path
    
    # 安全检查
    target_dir = os.path.abspath(target_dir)
    if not target_dir.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    os.makedirs(target_dir, exist_ok=True)
    
    # 安全的文件名
    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    if not filename:
        raise ValueError('Invalid filename')
    
    filepath = os.path.join(target_dir, filename)
    file.save(filepath)
    return filename

def get_file_for_download(username, project_id, filepath):
    """获取文件路径用于下载"""
    project_path = get_project_path(username, project_id)
    full_path = os.path.join(project_path, filepath)
    
    # 安全检查
    full_path = os.path.abspath(full_path)
    if not full_path.startswith(os.path.abspath(project_path)):
        raise PermissionError('Access denied')
    
    if not os.path.isfile(full_path):
        raise FileNotFoundError('File not found')
    
    return full_path

def get_project_stats(username, project_id):
    """获取项目统计信息"""
    project_path = get_project_path(username, project_id)
    
    if not os.path.exists(project_path):
        return {'files_count': 0, 'total_size': 0}
    
    files_count = 0
    total_size = 0
    
    for root, dirs, files in os.walk(project_path):
        files_count += len(files)
        for f in files:
            try:
                total_size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    
    return {
        'files_count': files_count,
        'total_size': total_size,
        'total_size_formatted': format_size(total_size)
    }

def get_user_storage(username):
    """获取用户存储使用情况"""
    user_path = get_user_path(username)
    
    if not os.path.exists(user_path):
        return {'used': 0, 'used_formatted': '0 B'}
    
    total_size = 0
    for root, dirs, files in os.walk(user_path):
        for f in files:
            try:
                total_size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    
    return {
        'used': total_size,
        'used_formatted': format_size(total_size)
    }
