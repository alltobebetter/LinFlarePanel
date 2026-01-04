#!/bin/bash

# CloudTunnel 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/alltobebetter/LinFlarePanel/main/setup.sh | bash
# 或:   wget -qO- https://raw.githubusercontent.com/alltobebetter/LinFlarePanel/main/setup.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# GitHub 仓库信息
REPO="alltobebetter/LinFlarePanel"
BRANCH="main"

# 安装目录
INSTALL_DIR="/opt/cloudtunnel"
DATA_DIR="/pjdata"

# ==================== 下载源配置 ====================

# 面板 ZIP 下载源（国内镜像优先）
ZIP_SOURCES=(
    "https://ghproxy.net/https://github.com/${REPO}/archive/${BRANCH}.zip"
    "https://gh.ddlc.top/https://github.com/${REPO}/archive/${BRANCH}.zip"
    "https://gh-proxy.com/https://github.com/${REPO}/archive/${BRANCH}.zip"
    "https://github.com/${REPO}/archive/${BRANCH}.zip"
)

# Git Clone 源（国内镜像优先）
CLONE_SOURCES=(
    "https://ghproxy.net/https://github.com/${REPO}.git"
    "https://gh.ddlc.top/https://github.com/${REPO}.git"
    "https://gh-proxy.com/https://github.com/${REPO}.git"
    "https://github.com/${REPO}.git"
)

# Cloudflared 下载源（国内镜像优先）
CF_MIRRORS=(
    "https://ghproxy.net/https://github.com"
    "https://gh.ddlc.top/https://github.com"
    "https://gh-proxy.com/https://github.com"
    "https://github.com"
)

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║      CloudTunnel 一键安装脚本 v2.0        ║"
echo "  ║   支持国内网络 / Docker容器 / 多架构      ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# ==================== 工具函数 ====================

# 打印带颜色的消息
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 测试 URL 是否可访问
test_url() {
    local url="$1"
    curl -sfI --connect-timeout 5 --max-time 10 "$url" >/dev/null 2>&1
}

# 下载文件（带进度条）
download_file() {
    local url="$1"
    local output="$2"
    curl -fL --connect-timeout 30 --max-time 600 --progress-bar -o "$output" "$url"
}

# ==================== 系统检测 ====================

detect_system() {
    log_info "检测系统环境..."
    
    # 检测操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PKG_MGR="brew"
    elif [ -f /etc/debian_version ]; then
        OS="debian"
        PKG_MGR="apt"
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
        PKG_MGR="yum"
    elif [ -f /etc/alpine-release ]; then
        OS="alpine"
        PKG_MGR="apk"
    else
        OS="linux"
        PKG_MGR=""
    fi
    
    # 检测架构
    ARCH=$(uname -m)
    case $ARCH in
        x86_64|amd64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        armv7l|armv7) ARCH="arm" ;;
        i386|i686) ARCH="386" ;;
        *) ARCH="amd64" ;;
    esac
    
    # 检测是否有 systemd
    if command -v systemctl &>/dev/null && [ -d /run/systemd/system ]; then
        HAS_SYSTEMD=true
    else
        HAS_SYSTEMD=false
    fi
    
    # 检测是否在容器内
    if [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null; then
        IN_CONTAINER=true
    else
        IN_CONTAINER=false
    fi
    
    echo -e "  系统: ${CYAN}$OS${NC} | 架构: ${CYAN}$ARCH${NC}"
    echo -e "  Systemd: ${CYAN}$HAS_SYSTEMD${NC} | 容器: ${CYAN}$IN_CONTAINER${NC}"
}

# ==================== 依赖安装 ====================

# 配置国内 APT 源
setup_apt_mirror() {
    if [ "$OS" != "debian" ]; then return; fi
    if grep -q "aliyun\|tuna\|ustc" /etc/apt/sources.list 2>/dev/null; then
        log_info "APT 源已配置"
        return
    fi
    
    log_info "配置国内 APT 镜像源..."
    
    # 获取版本代号
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        CODENAME=${VERSION_CODENAME:-bullseye}
    else
        CODENAME="bullseye"
    fi
    
    # 备份并替换
    cp /etc/apt/sources.list /etc/apt/sources.list.bak 2>/dev/null || true
    cat > /etc/apt/sources.list << EOF
deb https://mirrors.aliyun.com/debian/ ${CODENAME} main contrib non-free
deb https://mirrors.aliyun.com/debian/ ${CODENAME}-updates main contrib non-free
deb https://mirrors.aliyun.com/debian-security ${CODENAME}-security main contrib non-free
EOF
}

# 安装基础依赖
install_dependencies() {
    log_info "检查并安装依赖..."
    
    # 需要的命令
    local deps_needed=()
    
    command -v curl &>/dev/null || deps_needed+=("curl")
    command -v wget &>/dev/null || deps_needed+=("wget")
    command -v unzip &>/dev/null || deps_needed+=("unzip")
    command -v python3 &>/dev/null || deps_needed+=("python3")
    command -v git &>/dev/null || deps_needed+=("git")
    
    # 检查 pip/venv
    if ! python3 -m pip --version &>/dev/null 2>&1; then
        deps_needed+=("python3-pip")
    fi
    if ! python3 -m venv --help &>/dev/null 2>&1; then
        deps_needed+=("python3-venv")
    fi
    
    if [ ${#deps_needed[@]} -eq 0 ]; then
        log_info "所有依赖已安装"
        return
    fi
    
    log_info "安装: ${deps_needed[*]}"
    
    case $PKG_MGR in
        apt)
            setup_apt_mirror
            apt-get update -qq
            apt-get install -y -qq ${deps_needed[@]} 2>/dev/null || \
            apt-get install -y ${deps_needed[@]}
            ;;
        yum)
            yum install -y ${deps_needed[@]}
            ;;
        apk)
            apk add --no-cache ${deps_needed[@]} bash
            ;;
        brew)
            brew install ${deps_needed[@]}
            ;;
        *)
            log_error "未知包管理器，请手动安装: ${deps_needed[*]}"
            exit 1
            ;;
    esac
    
    log_info "依赖安装完成"
}

# ==================== Cloudflared 安装 ====================

install_cloudflared() {
    # 检查是否已安装
    if command -v cloudflared &>/dev/null; then
        local ver=$(cloudflared --version 2>&1 | head -1)
        log_info "cloudflared 已安装: $ver"
        return 0
    fi
    
    log_info "安装 cloudflared..."
    
    # 获取最新版本
    log_info "获取最新版本..."
    local version=""
    version=$(curl -sL --connect-timeout 10 "https://api.github.com/repos/cloudflare/cloudflared/releases/latest" 2>/dev/null | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
    
    if [ -z "$version" ]; then
        version="2024.12.2"
        log_warn "无法获取最新版本，使用 $version"
    else
        log_info "最新版本: $version"
    fi
    
    # 确定文件名
    local filename=""
    case $OS in
        debian) filename="cloudflared-linux-${ARCH}.deb" ;;
        rhel) filename="cloudflared-linux-${ARCH}.rpm" ;;
        macos)
            if [ "$ARCH" == "arm64" ]; then
                filename="cloudflared-darwin-arm64.tgz"
            else
                filename="cloudflared-darwin-amd64.tgz"
            fi
            ;;
        *) filename="cloudflared-linux-${ARCH}" ;;
    esac
    
    # 测试并下载
    log_info "测试下载源..."
    local download_url=""
    local base_path="/cloudflare/cloudflared/releases/download/${version}/${filename}"
    
    for mirror in "${CF_MIRRORS[@]}"; do
        local test_url="${mirror}${base_path}"
        echo -n "  测试 ${mirror%%/https*}... "
        if test_url "$test_url"; then
            echo -e "${GREEN}可用${NC}"
            download_url="$test_url"
            break
        else
            echo -e "${RED}不可用${NC}"
        fi
    done
    
    if [ -z "$download_url" ]; then
        log_error "所有下载源都不可用"
        exit 1
    fi
    
    # 下载
    log_info "下载 cloudflared..."
    local tmp_file="/tmp/${filename}"
    if ! download_file "$download_url" "$tmp_file"; then
        log_error "下载失败"
        exit 1
    fi
    
    # 安装
    log_info "安装 cloudflared..."
    case $OS in
        debian)
            dpkg -i "$tmp_file" 2>/dev/null || apt-get install -f -y
            ;;
        rhel)
            rpm -i "$tmp_file" 2>/dev/null || yum install -y "$tmp_file"
            ;;
        macos)
            cd /tmp && tar -xzf "$tmp_file"
            mv cloudflared /usr/local/bin/
            chmod +x /usr/local/bin/cloudflared
            ;;
        *)
            mv "$tmp_file" /usr/local/bin/cloudflared
            chmod +x /usr/local/bin/cloudflared
            ;;
    esac
    
    rm -f "$tmp_file"
    
    # 验证
    if command -v cloudflared &>/dev/null; then
        log_info "cloudflared 安装成功: $(cloudflared --version | head -1)"
    else
        log_error "cloudflared 安装失败"
        exit 1
    fi
}

# ==================== Cloudflare 登录和隧道 ====================

login_cloudflare() {
    if [ -f ~/.cloudflared/cert.pem ]; then
        log_info "已登录 Cloudflare"
        return 0
    fi
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${YELLOW}  登录 Cloudflare${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "接下来会显示一个授权链接"
    echo "请复制链接到浏览器完成授权"
    echo ""
    read -p "按 Enter 继续..."
    
    cloudflared tunnel login
}

create_tunnel() {
    local base_name="cloudtunnel"
    local tunnel_name=""
    local suffix=""
    
    # 生成随机4位后缀
    generate_suffix() {
        cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 4 | head -n 1
    }
    
    # 先尝试基础名称
    if cloudflared tunnel list 2>/dev/null | grep -q "^[a-f0-9-]\+\s\+${base_name}\s"; then
        TUNNEL_ID=$(cloudflared tunnel list | grep "${base_name}" | head -1 | awk '{print $1}')
        local cred_file="${HOME}/.cloudflared/${TUNNEL_ID}.json"
        
        if [ -f "$cred_file" ]; then
            tunnel_name="$base_name"
            log_info "使用已有隧道: $tunnel_name"
        else
            # 本地无凭证，创建新隧道
            suffix=$(generate_suffix)
            tunnel_name="${base_name}-${suffix}"
            log_info "创建新隧道: $tunnel_name"
            cloudflared tunnel create "$tunnel_name"
            TUNNEL_ID=$(cloudflared tunnel list | grep "$tunnel_name" | awk '{print $1}')
        fi
    else
        tunnel_name="$base_name"
        log_info "创建隧道: $tunnel_name"
        cloudflared tunnel create "$tunnel_name"
        TUNNEL_ID=$(cloudflared tunnel list | grep "$tunnel_name" | awk '{print $1}')
    fi
    
    log_info "隧道 ID: $TUNNEL_ID"
    
    # 保存隧道名供后续使用
    TUNNEL_NAME="$tunnel_name"
    
    # 创建基础配置
    mkdir -p ~/.cloudflared
    cat > ~/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${HOME}/.cloudflared/${TUNNEL_ID}.json

ingress:
  - service: http_status:404
EOF
}

# ==================== 面板下载和安装 ====================

download_panel() {
    # 检查是否已安装
    if [ -f "$INSTALL_DIR/app.py" ] && [ -d "$INSTALL_DIR/venv" ]; then
        log_info "面板已安装，跳过下载"
        return 0
    fi
    
    log_info "下载 CloudTunnel 面板..."
    
    mkdir -p $INSTALL_DIR
    mkdir -p $DATA_DIR
    [ -n "$SUDO_USER" ] && chown $SUDO_USER:$SUDO_USER $DATA_DIR
    
    cd /tmp
    rm -rf cloudtunnel LinFlarePanel-main cloudtunnel.zip 2>/dev/null || true
    
    local downloaded=false
    
    # 方法1: Git Clone
    if command -v git &>/dev/null && [ "$downloaded" = false ]; then
        log_info "尝试 git clone..."
        for src in "${CLONE_SOURCES[@]}"; do
            local short_name="${src%%/${REPO}*}"
            [ "$short_name" = "$src" ] && short_name="github.com"
            echo -n "  尝试 $short_name... "
            if git clone --depth 1 -q "$src" cloudtunnel 2>/dev/null; then
                echo -e "${GREEN}成功${NC}"
                cp -r cloudtunnel/* $INSTALL_DIR/
                rm -rf cloudtunnel
                downloaded=true
                break
            else
                echo -e "${RED}失败${NC}"
            fi
        done
    fi
    
    # 方法2: ZIP 下载
    if [ "$downloaded" = false ]; then
        log_info "尝试 ZIP 下载..."
        for src in "${ZIP_SOURCES[@]}"; do
            local short_name="${src%%/${REPO}*}"
            [ "$short_name" = "$src" ] && short_name="github.com"
            echo -n "  尝试 $short_name... "
            if curl -fsSL --connect-timeout 30 -o cloudtunnel.zip "$src" 2>/dev/null; then
                echo -e "${GREEN}成功${NC}"
                unzip -q cloudtunnel.zip
                cp -r LinFlarePanel-main/* $INSTALL_DIR/
                rm -rf cloudtunnel.zip LinFlarePanel-main
                downloaded=true
                break
            else
                echo -e "${RED}失败${NC}"
            fi
        done
    fi
    
    if [ "$downloaded" = false ]; then
        log_error "下载失败，请检查网络连接"
        exit 1
    fi
    
    log_info "面板下载完成"
}

install_panel() {
    log_info "安装面板依赖..."
    
    cd $INSTALL_DIR
    [ -n "$SUDO_USER" ] && chown -R $SUDO_USER:$SUDO_USER $INSTALL_DIR
    
    # 创建虚拟环境（如果不存在）
    if [ ! -d "venv" ]; then
        log_info "创建 Python 虚拟环境..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # 配置 pip 国内源
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ 2>/dev/null || true
    pip config set global.trusted-host mirrors.aliyun.com 2>/dev/null || true
    
    # 安装依赖
    log_info "安装 Python 依赖..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    
    deactivate
    
    log_info "面板安装完成"
}

# ==================== 服务配置 ====================

create_start_scripts() {
    log_info "创建启动脚本..."
    
    local home_dir="${HOME}"
    [ -n "$SUDO_USER" ] && home_dir=$(eval echo ~$SUDO_USER)
    
    # cloudflared 启动脚本
    cat > "${home_dir}/start_cloudflared.sh" << 'SCRIPT'
#!/bin/bash
if pgrep -f "cloudflared tunnel run" >/dev/null; then
    echo "Cloudflared 已在运行"
    exit 0
fi
nohup cloudflared tunnel run > /var/log/cloudflared.log 2>&1 &
echo $! > /tmp/cloudflared.pid
echo "Cloudflared 已启动 (PID: $!)"
SCRIPT
    chmod +x "${home_dir}/start_cloudflared.sh"
    
    # cloudflared 停止脚本
    cat > "${home_dir}/stop_cloudflared.sh" << 'SCRIPT'
#!/bin/bash
if [ -f /tmp/cloudflared.pid ]; then
    kill $(cat /tmp/cloudflared.pid) 2>/dev/null
    rm -f /tmp/cloudflared.pid
fi
pkill -f "cloudflared tunnel run" 2>/dev/null || true
echo "Cloudflared 已停止"
SCRIPT
    chmod +x "${home_dir}/stop_cloudflared.sh"
    
    # 面板启动脚本
    cat > "${home_dir}/start_cloudtunnel.sh" << SCRIPT
#!/bin/bash
if pgrep -f "python.*app.py" >/dev/null; then
    echo "CloudTunnel 已在运行"
    exit 0
fi
cd $INSTALL_DIR
source venv/bin/activate
nohup python app.py > /var/log/cloudtunnel.log 2>&1 &
echo \$! > /tmp/cloudtunnel.pid
echo "CloudTunnel 已启动 (PID: \$!)"
echo "访问: http://localhost:5000"
SCRIPT
    chmod +x "${home_dir}/start_cloudtunnel.sh"
    
    # 面板停止脚本
    cat > "${home_dir}/stop_cloudtunnel.sh" << 'SCRIPT'
#!/bin/bash
if [ -f /tmp/cloudtunnel.pid ]; then
    kill $(cat /tmp/cloudtunnel.pid) 2>/dev/null
    rm -f /tmp/cloudtunnel.pid
fi
pkill -f "python.*app.py" 2>/dev/null || true
echo "CloudTunnel 已停止"
SCRIPT
    chmod +x "${home_dir}/stop_cloudtunnel.sh"
    
    # 一键启动/停止全部
    cat > "${home_dir}/start_all.sh" << SCRIPT
#!/bin/bash
${home_dir}/start_cloudflared.sh
sleep 2
${home_dir}/start_cloudtunnel.sh
SCRIPT
    chmod +x "${home_dir}/start_all.sh"
    
    cat > "${home_dir}/stop_all.sh" << SCRIPT
#!/bin/bash
${home_dir}/stop_cloudtunnel.sh
${home_dir}/stop_cloudflared.sh
SCRIPT
    chmod +x "${home_dir}/stop_all.sh"
    
    [ -n "$SUDO_USER" ] && chown $SUDO_USER:$SUDO_USER "${home_dir}"/*.sh || true
}

create_systemd_services() {
    if [ "$HAS_SYSTEMD" = false ]; then
        log_warn "未检测到 systemd，仅创建启动脚本"
        create_start_scripts
        return
    fi
    
    log_info "创建 systemd 服务..."
    
    local run_user="${SUDO_USER:-$USER}"
    
    # cloudflared 服务
    cat > /etc/systemd/system/cloudflared.service << EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=${run_user}
ExecStart=$(which cloudflared) tunnel run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    # 面板服务
    cat > /etc/systemd/system/cloudtunnel.service << EOF
[Unit]
Description=CloudTunnel Panel
After=network.target cloudflared.service

[Service]
Type=simple
User=${run_user}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable cloudflared cloudtunnel 2>/dev/null || true
    
    # 同时创建脚本备用
    create_start_scripts
    
    log_info "systemd 服务创建完成"
}

# ==================== 域名配置 ====================

setup_domain() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${YELLOW}  配置面板访问域名${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "输入用于访问面板的域名（需托管在 Cloudflare）"
    echo "例如: panel.example.com"
    echo "直接回车跳过，仅本地访问"
    echo ""
    read -e -p "域名: " PANEL_DOMAIN
    
    if [ -z "$PANEL_DOMAIN" ]; then
        log_info "跳过域名配置"
        return
    fi
    
    # 更新隧道配置
    cat > ~/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${HOME}/.cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: ${PANEL_DOMAIN}
    service: http://localhost:5000
  - service: http_status:404
EOF

    # 配置 DNS
    log_info "配置 DNS 记录..."
    cloudflared tunnel route dns "$TUNNEL_NAME" "$PANEL_DOMAIN" 2>/dev/null || \
        log_warn "DNS 配置可能需要手动在 Cloudflare 面板完成"
    
    log_info "域名配置完成: https://${PANEL_DOMAIN}"
}

# ==================== 启动服务 ====================

start_services() {
    log_info "启动服务..."
    
    local home_dir="${HOME}"
    [ -n "$SUDO_USER" ] && home_dir=$(eval echo ~$SUDO_USER)
    
    if [ "$HAS_SYSTEMD" = true ]; then
        systemctl start cloudflared cloudtunnel 2>/dev/null || {
            log_warn "systemd 启动失败，使用脚本启动"
            bash "${home_dir}/start_all.sh"
        }
    else
        bash "${home_dir}/start_all.sh"
    fi
    
    sleep 3
}

# ==================== 完成信息 ====================

show_complete() {
    local home_dir="${HOME}"
    [ -n "$SUDO_USER" ] && home_dir=$(eval echo ~$SUDO_USER)
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       CloudTunnel 安装完成！              ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "本地访问: ${CYAN}http://localhost:5000${NC}"
    [ -n "$PANEL_DOMAIN" ] && echo -e "公网访问: ${CYAN}https://${PANEL_DOMAIN}${NC}"
    echo ""
    echo -e "默认账号: ${YELLOW}admin${NC}"
    echo -e "默认密码: ${YELLOW}admin${NC}"
    echo -e "${RED}请登录后立即修改密码！${NC}"
    echo ""
    echo "管理命令:"
    if [ "$HAS_SYSTEMD" = true ]; then
        echo "  systemctl status cloudtunnel    # 查看状态"
        echo "  systemctl restart cloudtunnel   # 重启面板"
        echo "  journalctl -u cloudtunnel -f    # 查看日志"
    else
        echo "  ${home_dir}/start_all.sh   # 启动全部"
        echo "  ${home_dir}/stop_all.sh    # 停止全部"
    fi
    echo ""
}

# ==================== 主流程 ====================

main() {
    # 检查 root 权限
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 root 权限运行此脚本"
        echo "用法: sudo bash setup.sh"
        exit 1
    fi
    
    detect_system
    install_dependencies
    install_cloudflared
    login_cloudflare
    create_tunnel
    download_panel
    install_panel
    create_systemd_services
    setup_domain
    start_services
    show_complete
}

main "$@"
