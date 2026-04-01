# Remote Term

手机远程控制电脑终端，iPhone Safari 直接访问，无需安装任何 App。内置 Web SSH 客户端，支持从浏览器直接 SSH 连接到任意服务器。

## 方案概述

自建 Web SSH 服务，手机通过浏览器填写 SSH 连接信息，即可操作远程终端。

```
iPhone Safari ---> Web SSH Server (Python) ---> SSH ---> 目标服务器
```

## 部署步骤

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
```

### 2. 启动服务

```bash
python server/server.py -p 8080
```

或使用 systemd 服务管理脚本：

```bash
./services/remote_term_service.sh install   # 安装并启用开机自启
./services/remote_term_service.sh start     # 启动服务
./services/remote_term_service.sh restart   # 重启服务
./services/remote_term_service.sh logs      # 查看日志
```

### 3. 配置防火墙

```bash
# 查看防火墙状态
sudo ufw status

# 允许局域网访问 8080 端口（推荐）
sudo ufw allow from 192.168.0.0/16 to any port 8080 proto tcp

# 或允许所有来源访问
sudo ufw allow 8080/tcp
```

### 4. 手机访问

iPhone 连接同一 WiFi，Safari 打开：

```
http://<电脑IP>:8080
```

在登录页面填写 SSH 连接信息（Host、Port、Username、Password），点击 Connect 即可。

查看电脑 IP：

```bash
hostname -I
```

## 互联网访问：Web SSH + frp

通过 frp 内网穿透，实现从任何网络用 iPhone Safari SSH 连接远程服务器。

```
iPhone Safari ---> VPS (frps :9080) ---> 被控电脑 (frpc) ---> Web SSH Server (:8080) ---> SSH ---> 目标服务器
```

### 1. VPS 端部署 frps

```bash
# 下载 frp（去 GitHub 查最新版本）
wget https://github.com/fatedier/frp/releases/download/v0.68.0/frp_0.68.0_linux_amd64.tar.gz
tar -xzf frp_0.68.0_linux_amd64.tar.gz
cd frp_0.68.0_linux_amd64
```

编辑 `frps.toml`：

```toml
bindPort = 7000

[auth]
token = "你的密钥"
```

启动：

```bash
./frps -c frps.toml
```

VPS 防火墙放行：

```bash
sudo ufw allow 7000/tcp   # frp 通信端口
sudo ufw allow 9080/tcp   # 映射出来的端口
```

### 2. 被控电脑端部署 frpc

同样下载 frp，编辑 `frpc.toml`：

```toml
serverAddr = "VPS公网IP"
serverPort = 7000

[auth]
token = "你的密钥"

[[proxies]]
name = "web-ssh"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8080
remotePort = 9080
```

启动（先启动 Web SSH Server，再启动 frpc）：

```bash
# 手动启动
python server/server.py -p 8080
./frpc -c frpc.toml

# 或使用 systemd 服务管理脚本
./services/remote_term_service.sh install && ./services/remote_term_service.sh start
./services/frpc_service.sh install && ./services/frpc_service.sh start
```

### 3. iPhone 访问

Safari 打开：

```
http://VPS公网IP:9080
```

在登录页面填写目标服务器的 SSH 信息即可连接。

## 功能特性

### SSH 连接

- 页面内 SSH 登录表单，填写 Host/Port/Username/Password 直接连接
- 连接失败显示错误信息，支持断开重连
- 状态栏提供 Disconnect 按钮

### 输入方式

- 点击终端区域唤起**系统原生键盘**输入
- 桌面端可直接使用物理键盘

### 快捷键栏

底部提供常用快捷键按钮，无需依赖系统键盘：

| 按键 | 功能 |
|------|------|
| Tab | 自动补全（左侧，占两行高） |
| Enter | 回车确认（右侧，占两行高） |
| Esc | 退出/取消 |
| ^C | 中断进程 |
| ^L | 清屏 |
| ^Z | 挂起进程 |
| ^W | 删除前一个单词 |

双击终端区域也可发送 Tab（自动补全）。

### tmux 快捷键

独立一行的 tmux 常用操作：

| 按键 | 功能 |
|------|------|
| ^B+D | 离开当前会话（detach） |
| ^B+( | 切换到上一个会话 |
| ^B+) | 切换到下一个会话 |
| ^B+S | 打开会话列表 |
| Clear | 清屏并清除 tmux 滚动缓冲区 |

### 方向键与翻页

- 方向键：◀ ▼ ▲ ▶
- PgUp / PgDn：翻页浏览

### 粘贴栏

- 底部独立粘贴栏：左侧输入框用于粘贴内容，右侧 Paste 按钮发送到终端
- 支持 Enter 键直接发送

### 终端滚动

- 在终端区域上下滑动可浏览历史输出（支持 5000 行回滚）
- 在 tmux（需 `set -g mouse on`）中触摸滑动同样有效
- 仅在 alternate buffer（tmux/vim/less）中发送鼠标滚轮序列，普通 shell 中不会产生乱码
- 滚到底部后继续上滑可过度滚动，将底部内容推到屏幕中部方便查看；下滑或有新输出时自动归位

### 复制粘贴

- 状态栏提供 **Select** / **Copy** 按钮
- 点击 **Select** 进入选择模式（按钮变黄），在终端区域拖动手指选中文本
- 选择模式下自动禁止键盘弹出，避免 resize 清除选区
- 点击 **Copy** 复制选中文本到剪贴板
- 再次点击 **Select** 退出选择模式，恢复正常输入

### 其他

- Tokyo Night 配色主题
- 状态栏显示连接状态和终端尺寸
- 服务端日志输出，方便排查连接问题

## 其他隧道方案

| 方案 | iPhone 零安装 | 难度 | 成本 |
|------|:---:|:---:|:---:|
| frp | ✓ | 中 | 需 VPS |
| Cloudflare Tunnel | ✓ | 低 | 免费（需域名） |
| Tailscale | ✗（需装 VPN App） | 低 | 免费 |

## 安全注意事项

- 互联网访问时**必须启用 HTTPS**（SSH 密码通过 WebSocket 传输）
- 建议在 VPS 上用 nginx 反向代理 + Let's Encrypt 加 HTTPS
- `auth.token` 两端必须一致，建议用 `openssl rand -hex 32` 生成随机密钥
- 生产环境建议用 systemd 管理进程，防止掉线
- 当前 SSH 连接不验证服务器 host key（`known_hosts=None`），请确保网络可信
