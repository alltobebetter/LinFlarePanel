import os
import yaml
import subprocess
import shutil
import requests
from pathlib import Path

# Cloudflared 配置路径
CLOUDFLARED_DIR = os.path.expanduser('~/.cloudflared')
CONFIG_PATH = os.path.join(CLOUDFLARED_DIR, 'config.yml')

def get_cloudflared_path():
    """获取 cloudflared 可执行文件路径"""
    return shutil.which('cloudflared')

def is_cloudflared_installed():
    """检查 cloudflared 是否安装"""
    return get_cloudflared_path() is not None

def load_tunnel_config():
    """加载隧道配置"""
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def save_tunnel_config(config):
    """保存隧道配置"""
    os.makedirs(CLOUDFLARED_DIR, exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def get_tunnel_info():
    """获取隧道信息"""
    config = load_tunnel_config()
    if not config:
        return None
    return {
        'tunnel_id': config.get('tunnel'),
        'credentials_file': config.get('credentials-file'),
        'ingress': config.get('ingress', [])
    }

def get_ingress_rules():
    """获取当前的 ingress 规则"""
    config = load_tunnel_config()
    if not config:
        return []
    
    rules = []
    for rule in config.get('ingress', []):
        if 'hostname' in rule:
            rules.append({
                'hostname': rule['hostname'],
                'service': rule['service']
            })
    return rules

def add_ingress_rule(subdomain, domain, port, protocol='http'):
    """添加 ingress 规则"""
    config = load_tunnel_config()
    if not config:
        raise ValueError('Tunnel config not found')
    
    hostname = f'{subdomain}.{domain}' if subdomain else domain
    service = f'{protocol}://localhost:{port}'
    
    new_rule = {
        'hostname': hostname,
        'service': service
    }
    
    # 检查是否已存在
    ingress = config.get('ingress', [])
    for rule in ingress:
        if rule.get('hostname') == hostname:
            raise ValueError(f'Rule for {hostname} already exists')
    
    # 在 catch-all 规则之前插入
    if ingress and 'hostname' not in ingress[-1]:
        ingress.insert(-1, new_rule)
    else:
        ingress.append(new_rule)
        # 确保有 catch-all 规则
        ingress.append({'service': 'http_status:404'})
    
    config['ingress'] = ingress
    save_tunnel_config(config)
    return True

def remove_ingress_rule(subdomain, domain):
    """移除 ingress 规则"""
    config = load_tunnel_config()
    if not config:
        raise ValueError('Tunnel config not found')
    
    hostname = f'{subdomain}.{domain}' if subdomain else domain
    
    ingress = config.get('ingress', [])
    new_ingress = [r for r in ingress if r.get('hostname') != hostname]
    
    if len(new_ingress) == len(ingress):
        raise ValueError(f'Rule for {hostname} not found')
    
    config['ingress'] = new_ingress
    save_tunnel_config(config)
    return True

def update_ingress_rule(subdomain, domain, port, protocol='http'):
    """更新 ingress 规则"""
    config = load_tunnel_config()
    if not config:
        raise ValueError('Tunnel config not found')
    
    hostname = f'{subdomain}.{domain}' if subdomain else domain
    service = f'{protocol}://localhost:{port}'
    
    ingress = config.get('ingress', [])
    found = False
    for rule in ingress:
        if rule.get('hostname') == hostname:
            rule['service'] = service
            found = True
            break
    
    if not found:
        raise ValueError(f'Rule for {hostname} not found')
    
    config['ingress'] = ingress
    save_tunnel_config(config)
    return True

# ============ 隧道服务管理 ============

def is_systemd_available():
    """检查 systemd 是否可用"""
    return os.path.exists('/run/systemd/system')

def get_tunnel_status():
    """获取隧道运行状态"""
    if is_systemd_available():
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'cloudflared'],
                capture_output=True, text=True
            )
            return result.stdout.strip() == 'active'
        except:
            pass
    
    # fallback: 检查进程
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'cloudflared'],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except:
        return False

def start_tunnel():
    """启动隧道"""
    if is_systemd_available():
        try:
            subprocess.run(['systemctl', 'start', 'cloudflared'], check=True)
            return True
        except subprocess.CalledProcessError:
            pass
    
    # fallback: 直接启动
    try:
        subprocess.Popen(
            ['cloudflared', 'tunnel', 'run'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True
    except:
        return False

def stop_tunnel():
    """停止隧道"""
    if is_systemd_available():
        try:
            subprocess.run(['systemctl', 'stop', 'cloudflared'], check=True)
            return True
        except subprocess.CalledProcessError:
            pass
    
    # fallback: kill 进程
    try:
        subprocess.run(['pkill', '-f', 'cloudflared'], check=True)
        return True
    except:
        return False

def restart_tunnel():
    """重启隧道"""
    if is_systemd_available():
        try:
            subprocess.run(['systemctl', 'restart', 'cloudflared'], check=True)
            return True
        except subprocess.CalledProcessError:
            pass
    
    # fallback
    stop_tunnel()
    import time
    time.sleep(1)
    return start_tunnel()

# ============ Cloudflare API ============

CF_API_BASE = 'https://api.cloudflare.com/client/v4'

def get_cf_zones(api_token):
    """获取 Cloudflare 账户下的所有域名"""
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        resp = requests.get(f'{CF_API_BASE}/zones', headers=headers, timeout=10)
        data = resp.json()
        
        if data.get('success'):
            return [zone['name'] for zone in data.get('result', [])]
        else:
            errors = data.get('errors', [])
            raise ValueError(errors[0].get('message', 'Unknown error') if errors else 'Unknown error')
    except requests.RequestException as e:
        raise ValueError(f'API request failed: {str(e)}')

def verify_cf_token(api_token):
    """验证 Cloudflare API Token"""
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        resp = requests.get(f'{CF_API_BASE}/user/tokens/verify', headers=headers, timeout=10)
        data = resp.json()
        return data.get('success', False)
    except:
        return False

def get_tunnel_list(api_token, account_id):
    """获取账户下的隧道列表"""
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        resp = requests.get(
            f'{CF_API_BASE}/accounts/{account_id}/cfd_tunnel',
            headers=headers, timeout=10
        )
        data = resp.json()
        
        if data.get('success'):
            return data.get('result', [])
        return []
    except:
        return []
