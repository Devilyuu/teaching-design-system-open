# 腾讯云轻量服务器部署说明

本文档用于把教学设计系统部署到腾讯云轻量应用服务器。推荐服务器系统为 Ubuntu 22.04 LTS 或 Debian 12。

如果服务器上已经部署了其他系统，例如“教师个人成果管理系统”，不要让本系统直接占用 `80` 端口。当前 Compose 配置已默认使用：

- 项目名：`teaching-design-system`
- 前端容器：`teaching-design-web`
- 后端容器：`teaching-design-api`
- 数据卷：`teaching-design-data`
- 对外端口：`8081`

这样它会和已有系统区分开来，先通过 `http://服务器公网IP:8081/` 访问。后续绑定域名时，再用反向代理把独立域名转发到 `127.0.0.1:8081`。

如果不用 Docker，而是和已有系统一样采用 Nginx + systemd 部署，建议使用：

```text
教学设计系统前端：http://服务器公网IP/design/
教学设计系统接口：http://服务器公网IP/design/api/
教学设计系统后端：127.0.0.1:8002
```

前端构建时使用：

```bash
VITE_BASE_PATH=/design/ VITE_API_BASE_URL=/design/api npm run build
```

AI 模型密钥使用独立的服务器加密密钥保护。生成一次 Fernet 密钥，并仅写入教学设计系统的 systemd 环境文件：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

环境变量名为 `MODEL_CONFIG_ENCRYPTION_KEY`。不要把实际密钥写入 Git、前端构建变量或聊天记录。密钥一旦用于保存模型配置就应持续备份；更换密钥前需要重新填写模型 API 密钥。

如果你准备直接用域名反向代理访问，而不希望公网直接访问 `8081`，启动前创建 `.env`：

```bash
cat > .env <<'EOF'
WEB_HOST=127.0.0.1
WEB_PORT=8081
EOF
```

## 1. 服务器准备

在腾讯云控制台开放防火墙端口：

- `22`：SSH 登录
- `8081`：本系统第一版网页访问
- `80`：如果已有系统正在使用，不要改动
- `443`：HTTPS，绑定域名后使用

登录服务器：

```bash
ssh root@你的服务器公网IP
```

安装 Docker 与 Compose 插件：

```bash
curl -fsSL https://get.docker.com | bash
systemctl enable --now docker
docker compose version
```

## 2. 拉取项目

```bash
mkdir -p /opt/teaching-design-system
cd /opt/teaching-design-system
git clone -b codex/mvp-outline-export-pr https://github.com/Devilyuu/teaching-design-system.git .
```

## 3. 启动服务

```bash
docker compose up -d --build
docker compose ps
```

打开：

```text
http://你的服务器公网IP:8081/
```

## 4. 后续更新

```bash
cd /opt/teaching-design-system
git pull
docker compose up -d --build
```

## 5. 数据与备份

系统数据存放在 Docker volume `teaching-design-data` 中，包含 SQLite 数据库和上传目录。备份命令示例：

```bash
mkdir -p /opt/backups
docker run --rm \
  -v teaching-design-data:/data \
  -v /opt/backups:/backup \
  alpine tar czf /backup/teaching-design-data-$(date +%F).tar.gz -C /data .
```

## 6. 与已有系统区分

推荐用独立子域名区分：

```text
成果管理系统：chengguo.example.com
教学设计系统：beike.example.com
```

如果服务器已有 Nginx，可以新增一个站点配置：

```nginx
server {
  listen 80;
  server_name beike.example.com;

  location / {
    proxy_pass http://127.0.0.1:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

这种方式建议 `.env` 使用：

```text
WEB_HOST=127.0.0.1
WEB_PORT=8081
```

这样 `8081` 不直接暴露在公网，只有 Nginx 可以访问它。

启用后：

```bash
nginx -t
systemctl reload nginx
```

## 7. 绑定域名和 HTTPS

第一版可以先用公网 IP 加端口访问。域名备案并解析到服务器后，建议再接入 Nginx Proxy Manager、Caddy 或 Certbot 配置 HTTPS。
