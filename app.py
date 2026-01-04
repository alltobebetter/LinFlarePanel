from flask import Flask, render_template, session, redirect, url_for, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import secrets
import os

from database import (
    init_db, create_user, verify_user, get_user_by_id, update_password,
    create_project, get_projects, get_project, delete_project,
    create_deployment, get_deployments, get_deployment, update_deployment_status, delete_deployment,
    add_log, get_logs, get_logs_count,
    get_setting, set_setting
)
from system_monitor import get_system_stats, get_hostname
from file_manager import (
    ensure_user_dir, create_project_dir, delete_project_dir,
    list_files, read_file, write_file, create_folder, delete_item, rename_item,
    save_upload, get_file_for_download, get_project_stats, get_user_storage
)
from tunnel_manager import (
    get_tunnel_info, get_ingress_rules, add_ingress_rule, remove_ingress_rule,
    get_tunnel_status, restart_tunnel, get_cf_zones, verify_cf_token
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化数据库
init_db()

# 创建默认管理员用户（如果不存在）
if not verify_user('admin', 'admin'):
    create_user('admin', 'admin')

def login_required(f):
    """登录验证装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    """获取当前登录用户"""
    if 'user_id' in session:
        return get_user_by_id(session['user_id'])
    return None

# ============ 页面路由 ============

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            ensure_user_dir(username)
            add_log(user['id'], 'INFO', f'用户 {username} 登录成功')
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        add_log(session['user_id'], 'INFO', f'用户 {session.get("username")} 退出登录')
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    system_stats = get_system_stats()
    projects = get_projects(user['id'])
    deployments = get_deployments(user['id'])
    active_deploys = len([d for d in deployments if d['status'] == 'running'])
    
    return render_template('dashboard.html',
                         user=user['username'],
                         system_stats=system_stats,
                         project_count=len(projects),
                         deploy_count=len(deployments),
                         active_deploys=active_deploys)

@app.route('/projects')
@login_required
def projects():
    user = get_current_user()
    projects_list = get_projects(user['id'])
    
    # 获取每个项目的文件统计
    for p in projects_list:
        stats = get_project_stats(user['username'], p['id'])
        p['files_count'] = stats['files_count']
        p['modified'] = p['created_at'][:10] if p['created_at'] else ''
    
    storage = get_user_storage(user['username'])
    
    return render_template('projects.html',
                         user=user['username'],
                         projects=projects_list,
                         storage=storage)

@app.route('/projects/<project_id>')
@login_required
def project_files(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return redirect(url_for('projects'))
    
    subpath = request.args.get('path', '')
    files_list = list_files(user['username'], project_id, subpath)
    
    return render_template('files.html',
                         user=user['username'],
                         project=project,
                         current_path=subpath,
                         files=files_list)

@app.route('/deploy')
@login_required
def deploy():
    user = get_current_user()
    projects_list = get_projects(user['id'])
    deployments = get_deployments(user['id'])
    
    # 获取域名列表
    cf_token = get_setting(user['id'], 'cf_api_token')
    domains = []
    if cf_token:
        try:
            domains = get_cf_zones(cf_token)
        except:
            pass
    
    tunnel_info = get_tunnel_info()
    tunnel_status = get_tunnel_status()
    
    # 格式化部署数据
    for d in deployments:
        d['project'] = d.get('project_name', '未关联项目')
    
    return render_template('deploy.html',
                         user=user['username'],
                         domains=domains,
                         projects=projects_list,
                         deployments=deployments,
                         tunnel_name=tunnel_info.get('tunnel_id', '') if tunnel_info else '',
                         tunnel_status='running' if tunnel_status else 'stopped',
                         active_connections=len([d for d in deployments if d['status'] == 'running']))

@app.route('/terminal')
@login_required
def terminal():
    user = get_current_user()
    return render_template('terminal.html',
                         user=user['username'],
                         hostname=get_hostname())

@app.route('/logs')
@login_required
def logs():
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    level = request.args.get('level', '')
    per_page = 20
    
    logs_list = get_logs(user['id'], level if level else None, per_page, (page - 1) * per_page)
    total = get_logs_count(user['id'], level if level else None)
    total_pages = (total + per_page - 1) // per_page
    
    # 格式化日志
    for log in logs_list:
        log['time'] = log['created_at']
    
    return render_template('logs.html',
                         user=user['username'],
                         logs=logs_list,
                         page=page,
                         total_pages=total_pages)

@app.route('/settings')
@login_required
def settings():
    user = get_current_user()
    tunnel_info = get_tunnel_info()
    cf_token = get_setting(user['id'], 'cf_api_token')
    
    return render_template('settings.html',
                         user=user['username'],
                         tunnel_id=tunnel_info.get('tunnel_id', '') if tunnel_info else '',
                         has_cf_token=bool(cf_token))

# ============ API 路由 ============

@app.route('/api/projects', methods=['POST'])
@login_required
def api_create_project():
    user = get_current_user()
    data = request.json
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({'error': '项目名称不能为空'}), 400
    
    project_id = create_project(user['id'], name, description)
    create_project_dir(user['username'], project_id)
    add_log(user['id'], 'INFO', f'创建项目: {name}')
    
    return jsonify({'id': project_id, 'name': name})

@app.route('/api/projects/<project_id>', methods=['DELETE'])
@login_required
def api_delete_project(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    delete_project(project_id, user['id'])
    delete_project_dir(user['username'], project_id)
    add_log(user['id'], 'INFO', f'删除项目: {project["name"]}')
    
    return jsonify({'success': True})

@app.route('/api/projects/<project_id>/files', methods=['GET'])
@login_required
def api_list_files(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    subpath = request.args.get('path', '')
    try:
        files = list_files(user['username'], project_id, subpath)
        return jsonify(files)
    except PermissionError:
        return jsonify({'error': '访问被拒绝'}), 403

@app.route('/api/projects/<project_id>/files/read', methods=['GET'])
@login_required
def api_read_file(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    filepath = request.args.get('path', '')
    try:
        content = read_file(user['username'], project_id, filepath)
        return jsonify({'content': content})
    except FileNotFoundError:
        return jsonify({'error': '文件不存在'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except PermissionError:
        return jsonify({'error': '访问被拒绝'}), 403

@app.route('/api/projects/<project_id>/files/write', methods=['POST'])
@login_required
def api_write_file(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    data = request.json
    filepath = data.get('path', '')
    content = data.get('content', '')
    
    try:
        write_file(user['username'], project_id, filepath, content)
        add_log(user['id'], 'INFO', f'编辑文件: {filepath}')
        return jsonify({'success': True})
    except PermissionError:
        return jsonify({'error': '访问被拒绝'}), 403

@app.route('/api/projects/<project_id>/files/upload', methods=['POST'])
@login_required
def api_upload_file(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    
    file = request.files['file']
    subpath = request.form.get('path', '')
    
    try:
        filename = save_upload(user['username'], project_id, subpath, file)
        add_log(user['id'], 'INFO', f'上传文件: {filename}')
        return jsonify({'filename': filename})
    except (PermissionError, ValueError) as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/files/download', methods=['GET'])
@login_required
def api_download_file(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    filepath = request.args.get('path', '')
    try:
        full_path = get_file_for_download(user['username'], project_id, filepath)
        return send_file(full_path, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': '文件不存在'}), 404
    except PermissionError:
        return jsonify({'error': '访问被拒绝'}), 403

@app.route('/api/projects/<project_id>/files/delete', methods=['POST'])
@login_required
def api_delete_file(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    data = request.json
    itempath = data.get('path', '')
    
    try:
        delete_item(user['username'], project_id, itempath)
        add_log(user['id'], 'INFO', f'删除: {itempath}')
        return jsonify({'success': True})
    except (FileNotFoundError, PermissionError) as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/projects/<project_id>/files/folder', methods=['POST'])
@login_required
def api_create_folder(project_id):
    user = get_current_user()
    project = get_project(project_id, user['id'])
    
    if not project:
        return jsonify({'error': '项目不存在'}), 404
    
    data = request.json
    folderpath = data.get('path', '')
    
    try:
        create_folder(user['username'], project_id, folderpath)
        add_log(user['id'], 'INFO', f'创建文件夹: {folderpath}')
        return jsonify({'success': True})
    except PermissionError:
        return jsonify({'error': '访问被拒绝'}), 403

# ============ 部署 API ============

@app.route('/api/deploy', methods=['POST'])
@login_required
def api_create_deployment():
    user = get_current_user()
    data = request.json
    
    project_id = data.get('project_id')
    subdomain = data.get('subdomain', '').strip()
    domain = data.get('domain', '').strip()
    port = data.get('port')
    
    if not all([subdomain, domain, port]):
        return jsonify({'error': '请填写完整信息'}), 400
    
    try:
        port = int(port)
    except:
        return jsonify({'error': '端口必须是数字'}), 400
    
    # 添加到数据库
    deploy_id = create_deployment(user['id'], project_id, subdomain, domain, port)
    
    # 添加到 cloudflared 配置
    try:
        add_ingress_rule(subdomain, domain, port)
        restart_tunnel()
        update_deployment_status(deploy_id, 'running')
        add_log(user['id'], 'INFO', f'创建部署: {subdomain}.{domain}')
    except Exception as e:
        add_log(user['id'], 'ERROR', f'部署失败: {str(e)}')
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'id': deploy_id})

@app.route('/api/deploy/<int:deploy_id>', methods=['DELETE'])
@login_required
def api_delete_deployment(deploy_id):
    user = get_current_user()
    deployment = get_deployment(deploy_id, user['id'])
    
    if not deployment:
        return jsonify({'error': '部署不存在'}), 404
    
    # 从 cloudflared 配置移除
    try:
        remove_ingress_rule(deployment['subdomain'], deployment['domain'])
        restart_tunnel()
    except Exception as e:
        add_log(user['id'], 'WARNING', f'移除隧道规则失败: {str(e)}')
    
    delete_deployment(deploy_id, user['id'])
    add_log(user['id'], 'INFO', f'删除部署: {deployment["subdomain"]}.{deployment["domain"]}')
    
    return jsonify({'success': True})

@app.route('/api/deploy/<int:deploy_id>/start', methods=['POST'])
@login_required
def api_start_deployment(deploy_id):
    user = get_current_user()
    deployment = get_deployment(deploy_id, user['id'])
    
    if not deployment:
        return jsonify({'error': '部署不存在'}), 404
    
    try:
        add_ingress_rule(deployment['subdomain'], deployment['domain'], deployment['port'])
        restart_tunnel()
        update_deployment_status(deploy_id, 'running')
        add_log(user['id'], 'INFO', f'启动部署: {deployment["subdomain"]}.{deployment["domain"]}')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deploy/<int:deploy_id>/stop', methods=['POST'])
@login_required
def api_stop_deployment(deploy_id):
    user = get_current_user()
    deployment = get_deployment(deploy_id, user['id'])
    
    if not deployment:
        return jsonify({'error': '部署不存在'}), 404
    
    try:
        remove_ingress_rule(deployment['subdomain'], deployment['domain'])
        restart_tunnel()
        update_deployment_status(deploy_id, 'stopped')
        add_log(user['id'], 'INFO', f'停止部署: {deployment["subdomain"]}.{deployment["domain"]}')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ 设置 API ============

@app.route('/api/settings/password', methods=['POST'])
@login_required
def api_change_password():
    user = get_current_user()
    data = request.json
    
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not old_password or not new_password:
        return jsonify({'error': '请填写完整信息'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '新密码至少6位'}), 400
    
    if update_password(user['id'], old_password, new_password):
        add_log(user['id'], 'INFO', '修改密码成功')
        return jsonify({'success': True})
    else:
        return jsonify({'error': '当前密码错误'}), 400

@app.route('/api/settings/cf_token', methods=['POST'])
@login_required
def api_set_cf_token():
    user = get_current_user()
    data = request.json
    token = data.get('token', '').strip()
    
    if not token:
        return jsonify({'error': 'Token 不能为空'}), 400
    
    if not verify_cf_token(token):
        return jsonify({'error': 'Token 无效'}), 400
    
    set_setting(user['id'], 'cf_api_token', token)
    add_log(user['id'], 'INFO', '更新 Cloudflare API Token')
    
    return jsonify({'success': True})

@app.route('/api/settings/domains', methods=['GET'])
@login_required
def api_get_domains():
    user = get_current_user()
    cf_token = get_setting(user['id'], 'cf_api_token')
    
    if not cf_token:
        return jsonify({'error': '未配置 Cloudflare API Token'}), 400
    
    try:
        domains = get_cf_zones(cf_token)
        return jsonify(domains)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tunnel/restart', methods=['POST'])
@login_required
def api_restart_tunnel():
    user = get_current_user()
    
    try:
        restart_tunnel()
        add_log(user['id'], 'INFO', '重启隧道')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/stats', methods=['GET'])
@login_required
def api_system_stats():
    return jsonify(get_system_stats())

# ============ WebSocket 终端 ============

terminal_processes = {}

@socketio.on('connect', namespace='/terminal')
def terminal_connect():
    if 'user_id' not in session:
        return False
    emit('output', {'data': f'Connected to {get_hostname()}\r\n'})

@socketio.on('input', namespace='/terminal')
def terminal_input(data):
    if 'user_id' not in session:
        return
    
    sid = request.sid
    if sid not in terminal_processes:
        import pty
        import subprocess
        import select
        import threading
        
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            ['/bin/bash'],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid
        )
        terminal_processes[sid] = {
            'process': process,
            'master_fd': master_fd
        }
        
        def read_output():
            while True:
                try:
                    if select.select([master_fd], [], [], 0.1)[0]:
                        output = os.read(master_fd, 1024)
                        if output:
                            socketio.emit('output', {'data': output.decode('utf-8', errors='replace')}, 
                                        namespace='/terminal', room=sid)
                except:
                    break
        
        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()
    
    master_fd = terminal_processes[sid]['master_fd']
    os.write(master_fd, data.encode())

@socketio.on('disconnect', namespace='/terminal')
def terminal_disconnect():
    sid = request.sid
    if sid in terminal_processes:
        try:
            terminal_processes[sid]['process'].terminate()
            os.close(terminal_processes[sid]['master_fd'])
        except:
            pass
        del terminal_processes[sid]

@socketio.on('resize', namespace='/terminal')
def terminal_resize(data):
    sid = request.sid
    if sid in terminal_processes:
        import fcntl
        import termios
        import struct
        
        master_fd = terminal_processes[sid]['master_fd']
        winsize = struct.pack('HHHH', data['rows'], data['cols'], 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
