# Remote Term

手机远程控制电脑终端，iPhone Safari 直接访问，无需安装任何 App。

## 方案概述

使用 **ttyd** 在被控电脑上启动 Web 终端服务，手机通过浏览器访问操作。

```
被控电脑 (ttyd) <--- WebSocket ---> iPhone Safari (xterm.js)
```

## 部署步骤

### 1. 安装 ttyd

```bash
sudo apt install ttyd
```

### 2. 启动服务

```bash
# 基本启动
ttyd -p 8080 bash

# 带密码保护（推荐）
ttyd -p 8080 -c 用户名:密码 bash

# 带 SSL 加密
ttyd -p 8080 -S -C cert.pem -K key.pem -c 用户名:密码 bash
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

查看电脑 IP：

```bash
hostname -I
```

## 互联网访问：ttyd + frp

通过 frp 内网穿透，实现从任何网络用 iPhone Safari 访问被控电脑终端。

```
iPhone Safari ---> VPS (frps :9080) ---> 被控电脑 (frpc) ---> ttyd (:8080)
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
sudo ufw allow 9080/tcp   # 映射出来的 ttyd 端口
```

### 2. 被控电脑端部署 frpc

同样下载 frp，编辑 `frpc.toml`：

```toml
serverAddr = "VPS公网IP"
serverPort = 7000

[auth]
token = "你的密钥"

[[proxies]]
name = "web-terminal"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8080
remotePort = 9080
```

启动（先启动 ttyd，再启动 frpc）：

```bash
ttyd -p 8080 -c 用户名:密码 bash
./frpc -c frpc.toml
```

### 3. iPhone 访问

Safari 打开：

```
http://VPS公网IP:9080
```

输入 ttyd 的用户名和密码即可操作终端。

## 自定义移动端界面

本项目提供了针对手机优化的自定义终端页面（`web/index.html`），上半屏为终端窗口，下半屏为虚拟键盘。

### 使用方式

```bash
# 用自定义页面启动 ttyd
ttyd -p 8080 -I web/index.html -c 用户名:密码 bash
```

### 功能特性

**虚拟键盘**

- **修饰键**：Ctrl / Alt / Shift / Fn（单击激活，按键后自动释放）
- **三层布局**：ABC（字母）、123（数字/标点）、!@#（符号）
- **Fn 层**：F1-F12、Home/End、PgUp/PgDn
- **方向键**：始终可见

**终端滚动**

- 在终端区域上下滑动可浏览历史输出（支持 5000 行回滚）
- Fn 层提供滚动按钮：▲Ln/▼Ln（单行）、▲5Ln/▼5Ln（5行）、Top/Btm（顶底）
- 滚动按钮同时发送鼠标滚轮序列，在 tmux（需 `set -g mouse on`）中同样有效

**复制粘贴**

- 状态栏提供 **Select** / **Copy** / **Paste** 三个按钮
- 点击 **Select** 进入选择模式（按钮变黄），在终端区域拖动手指选中文本
- 点击 **Copy** 复制选中文本到剪贴板
- 点击 **Paste** 从剪贴板读取内容并发送到终端
- 再次点击 **Select** 退出选择模式，恢复滑动滚动

**桌面端兼容**

- 在电脑浏览器访问时可正常使用物理键盘输入
- 仅在移动端禁用原生键盘弹出，避免与虚拟键盘冲突

**其他**

- Tokyo Night 配色主题
- 触摸终端区域不会唤起手机原生键盘
- 断线自动重连（3 秒间隔）
- 状态栏显示连接状态和终端尺寸

## 其他隧道方案

| 方案 | iPhone 零安装 | 难度 | 成本 |
|------|:---:|:---:|:---:|
| frp | ✓ | 中 | 需 VPS |
| Cloudflare Tunnel | ✓ | 低 | 免费（需域名） |
| Tailscale | ✗（需装 VPN App） | 低 | 免费 |

## 安全注意事项

- **不要**将 ttyd 直接暴露到公网，必须通过隧道访问
- 始终启用密码认证（`-c` 参数）
- 互联网访问时必须启用 HTTPS
- `auth.token` 两端必须一致，建议用 `openssl rand -hex 32` 生成随机密钥
- 生产环境建议用 systemd 管理 frps/frpc 进程，防止掉线
- 建议在 VPS 上用 nginx 反向代理 + Let's Encrypt 加 HTTPS