# CloudTunnel

Cloudflare 隧道管理面板，无需公网 IP 即可将本地服务暴露到公网。

## 功能

- 系统监控（CPU、内存、磁盘、网络）
- 项目文件管理（上传、下载、在线编辑）
- Cloudflare 隧道部署管理
- Web 终端
- 操作日志

## 一键安装

```bash
curl -fsSL https://your-domain.com/install.sh | bash
```

或手动安装：

```bash
git clone https://github.com/your-repo/cloudtunnel.git
cd cloudtunnel
chmod +x install.sh
./install.sh
```

## 手动启动

```bash
chmod +x start.sh
./start.sh
```

## 默认账号

- 用户名: `admin`
- 密码: `admin`

**请登录后立即修改密码！**

## 系统要求

- Linux (Debian/Ubuntu/CentOS) 或 macOS
- Python 3.8+
- Cloudflare 账号（免费即可）

## 管理命令

```bash
# 查看面板状态
sudo systemctl status cloudtunnel

# 重启面板
sudo systemctl restart cloudtunnel

# 查看隧道状态
sudo systemctl status cloudflared

# 重启隧道
sudo systemctl restart cloudflared

# 查看日志
sudo journalctl -u cloudtunnel -f
```

## 目录结构

```
/opt/cloudtunnel/    # 面板程序
/pjdata/             # 用户项目数据
~/.cloudflared/      # Cloudflare 隧道配置
```
