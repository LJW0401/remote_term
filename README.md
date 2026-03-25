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

## 互联网访问（后续阶段）

局域网部署完成后，可通过以下隧道方案实现互联网访问：

| 方案 | iPhone 零安装 | 难度 | 成本 |
|------|:---:|:---:|:---:|
| Cloudflare Tunnel | ✓ | 低 | 免费（需域名） |
| Tailscale | ✗（需装 VPN App） | 低 | 免费 |
| frp | ✓ | 中 | 需 VPS |

## 安全注意事项

- **不要**将 ttyd 直接暴露到公网，必须通过隧道访问
- 始终启用密码认证（`-c` 参数）
- 互联网访问时必须启用 HTTPS
- 建议限制局域网 IP 段访问