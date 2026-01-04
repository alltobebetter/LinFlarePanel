import psutil
import platform
import socket
from datetime import datetime, timedelta

def get_system_stats():
    """获取系统状态信息"""
    
    # CPU 信息
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()
    
    # 尝试获取 CPU 温度
    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    cpu_temp = entries[0].current
                    break
    except:
        pass
    
    # 内存信息
    memory = psutil.virtual_memory()
    
    # 磁盘信息
    disk = psutil.disk_usage('/')
    
    # 网络信息
    net_io = psutil.net_io_counters()
    
    # 系统运行时间
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    uptime_str = format_uptime(uptime)
    
    # 系统负载
    try:
        load = psutil.getloadavg()
    except:
        load = [0, 0, 0]
    
    return {
        'cpu': {
            'usage': cpu_percent,
            'cores': cpu_count,
            'model': get_cpu_model(),
            'temp': cpu_temp or 0
        },
        'memory': {
            'used': round(memory.used / (1024**3), 1),
            'total': round(memory.total / (1024**3), 1),
            'usage': memory.percent
        },
        'disk': {
            'used': round(disk.used / (1024**3), 1),
            'total': round(disk.total / (1024**3), 1),
            'usage': round(disk.percent, 1)
        },
        'network': {
            'upload': round(net_io.bytes_sent / (1024**2), 1),
            'download': round(net_io.bytes_recv / (1024**2), 1)
        },
        'uptime': uptime_str,
        'load': [round(l, 2) for l in load],
        'processes': len(psutil.pids()),
        'tcp_connections': len(psutil.net_connections(kind='tcp')),
        'boot_time': boot_time.strftime('%Y-%m-%d')
    }

def get_cpu_model():
    """获取 CPU 型号"""
    try:
        if platform.system() == 'Linux':
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        return line.split(':')[1].strip()
        elif platform.system() == 'Windows':
            import subprocess
            result = subprocess.run(
                ['wmic', 'cpu', 'get', 'name'],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                return lines[1].strip()
    except:
        pass
    return platform.processor() or 'Unknown'

def format_uptime(delta):
    """格式化运行时间"""
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f'{days}天')
    if hours > 0:
        parts.append(f'{hours}小时')
    parts.append(f'{minutes}分钟')
    
    return ' '.join(parts)

def get_hostname():
    """获取主机名"""
    return socket.gethostname()

def get_network_speed():
    """获取实时网络速度（需要两次采样）"""
    net1 = psutil.net_io_counters()
    import time
    time.sleep(1)
    net2 = psutil.net_io_counters()
    
    upload_speed = (net2.bytes_sent - net1.bytes_sent) / 1024  # KB/s
    download_speed = (net2.bytes_recv - net1.bytes_recv) / 1024  # KB/s
    
    return {
        'upload': round(upload_speed, 1),
        'download': round(download_speed, 1)
    }
