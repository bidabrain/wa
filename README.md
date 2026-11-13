# WA-TG Bridge

把 WhatsApp 消息转发到 Telegram 的一体化 Docker 镜像，所有操作都在网页里完成：

- **安卓模拟器 + 官方 WhatsApp**：浏览器里直接看到并操作安卓画面（noVNC），一键下载安装 whatsapp.com 官方 APK，在网页里完成注册登录。
- **[watgbridge](https://github.com/akshettrj/watgbridge)**：以「关联设备」身份登录你的 WhatsApp，把消息转发到 Telegram 超级群组的话题中，支持从 Telegram 回复。
- **图形化配置**：Telegram 机器人、群组、各类转发开关都用表单填写，也可以直接编辑 YAML。
- **按需开机**：模拟器只在关联授权或保活时才需要运行，平时关掉就行。支持定期**自动开机保活**和 **Telegram 提醒**，防止关联设备因主手机长期离线（约 14 天）被注销；关联失效时自动停止转发并通知你。
- **在线更新**：watgbridge 可在面板中更新（官方 Release / 源码编译 / 上传二进制），失败自动回滚，**无需重建镜像**；模拟器里的 WhatsApp 可一键检查更新（覆盖安装，不丢登录）。
- **中英双语界面**：右上角切换中文 / English。

```
┌──────────────────────── Docker 容器 ────────────────────────┐
│ 管理面板 :8080 (FastAPI)                                     │
│   ├─ noVNC 网页画面 ──WebSocket──> x11vnc ─> Xvfb ─> 安卓模拟器 │
│   ├─ 配对工具 wapair (配对码 / 二维码)                         │
│   └─ supervisord 控制 ─> watgbridge ──> Telegram Bot API     │
│ /data：配置、WhatsApp 会话、模拟器磁盘、日志                   │
└─────────────────────────────────────────────────────────────┘
```

## 运行要求

| 项目 | 说明 |
| --- | --- |
| CPU 架构 | x86_64 (amd64) |
| KVM | 运行安卓模拟器**必须**有 `/dev/kvm`。Linux 物理机/支持嵌套虚拟化的 VPS；Windows 用 Docker Desktop (WSL2) 时需开启嵌套虚拟化。没有 KVM 时转发服务照常可用，只是不能运行模拟器，可改用实体手机扫码。 |
| 内存 | 模拟器运行时约 3–4 GB，关闭后只剩转发服务（约 100 MB） |
| 磁盘 | 镜像约 6–8 GB，数据约 6 GB（模拟器 userdata） |

检查 KVM：`ls -l /dev/kvm`，或 `sudo apt install cpu-checker && kvm-ok`。

## 安装

### 方式一：使用预编译镜像（推荐）

镜像由 GitHub Actions 自动构建并发布在 `ghcr.io/bidabrain/wa:latest`，服务器上无需下载源码、无需本地编译。

1. 新建一个目录，创建 `docker-compose.yml`：

   ```bash
   mkdir -p ~/wa-tg-bridge && cd ~/wa-tg-bridge
   ```

   ```yaml
   services:
     wa-tg-bridge:
       image: ghcr.io/bidabrain/wa:latest
       container_name: wa-tg-bridge
       restart: unless-stopped
       ports:
         - "8080:8080"
       environment:
         WEB_PASSWORD: "change-me"   # 管理面板密码，务必修改
         TZ: Asia/Shanghai
       devices:
         - /dev/kvm:/dev/kvm         # 宿主机没有 KVM 时删除这两行
       volumes:
         - ./data:/data
   ```

2. 拉取镜像并启动（镜像约 6–8 GB，首次拉取需要一些时间）：

   ```bash
   docker compose pull
   ```

   ```bash
   docker compose up -d
   ```

3. 浏览器打开 `http://服务器IP:8080`，用 `WEB_PASSWORD` 登录。

**更新镜像**（数据都在 `data/`，不受影响）：

```bash
docker compose pull && docker compose up -d
```

> 只是更新 watgbridge 的话不需要更新镜像，直接在面板「版本更新」页操作即可，见下文「更新」。

如果拉取时报 `unauthorized` / `denied`，说明 GHCR 上的镜像包还是私有的：在 GitHub 个人主页 → Packages → `wa` → Package settings → Change visibility 设为 Public；或者在服务器上先用有 `read:packages` 权限的 Personal Access Token 执行 `docker login ghcr.io -u bidabrain`。

### 方式二：docker run

```bash
docker run -d --name wa-tg-bridge --restart unless-stopped \
  -p 8080:8080 --device /dev/kvm \
  -e WEB_PASSWORD=change-me -e TZ=Asia/Shanghai \
  -v $PWD/data:/data ghcr.io/bidabrain/wa:latest
```

### 方式三：从源码自行构建

```bash
git clone https://github.com/bidabrain/wa.git wa-tg-bridge && cd wa-tg-bridge
```

修改 `docker-compose.yml` 里的 `WEB_PASSWORD` 后：

```bash
docker compose up -d --build
```

Fork 本仓库后推送到 `main`，`.github/workflows/docker.yml` 会自动构建并发布到你自己的 `ghcr.io/<用户名>/<仓库名>`。

---

未设置 `WEB_PASSWORD` 时会自动生成密码，见 `docker logs wa-tg-bridge` 或 `data/.web_password`。

> 管理面板可以直接操作你的 WhatsApp，**不要在公网裸奔**：请设置强密码，最好放在反向代理（HTTPS）或 Tailscale/WireGuard 之后。

## 使用步骤

面板「概览」页有设置向导，按顺序完成即可：

1. **转发配置**：填写 Telegram Bot Token、你的用户 ID、目标超级群组 ID。
   - 在 @BotFather 创建机器人；
   - 新建超级群组，在群设置里开启「话题 (Topics)」；
   - 把机器人加入群组并设为管理员（需要「管理话题」权限）；
   - 先私聊机器人发送 `/start`，否则它无法给你发消息。
2. **安卓手机**：点「启动」，首次开机约 1–3 分钟；然后点「下载并安装官方 WhatsApp」。
3. 在网页画面中打开 WhatsApp，用你的号码注册，输入短信/电话验证码（可用「向模拟器输入文字」发送）。
   > WhatsApp 一个号码只能有一台主手机。在模拟器注册后，原手机上的 WhatsApp 会被登出；原手机之后可以作为「配套设备」重新关联到这个账号。
4. **WhatsApp 关联**：输入手机号，选「配对码」，面板显示 8 位码；在模拟器 WhatsApp 中点击弹出的通知（或 ⋮ → 已关联的设备 → 关联新设备 → 改用电话号码关联）输入该码。成功后转发服务自动启动。
5. 回到「安卓手机」点「关机」。之后转发独立运行。
6. **保活与提醒**：建议开启「自动保活」（例如每 7 天开机 20 分钟），或开启 Telegram 提醒，自己定期打开。

## 关联过期后重新授权

安卓模拟器的磁盘（包括已登录的 WhatsApp）永久保存在 `data/android/`，关机就像手机关机，下次启动 WhatsApp 依然是登录状态。

关联失效时，面板会自动停止转发、在概览页标记「已失效」，并通过 Telegram 机器人通知你。重新授权步骤：

1. 「安卓手机」→ 启动，等待开机；
2. 「WhatsApp 关联」→ 输入手机号 → 开始关联，在模拟器 WhatsApp 中输入 8 位配对码。

> 模拟器没有摄像头，不能扫二维码；配对码与扫码效果完全相同。二维码方式仅用于另一台实体手机扫码。

## 更新

**watgbridge（不需要重建镜像）**：面板「版本更新」页提供三种方式：

| 方式 | 说明 |
| --- | --- |
| 官方预编译 Release | 从 GitHub Release 下载 `watgbridge_linux_amd64`，几秒完成。只替换转发程序。 |
| 从源码编译 | 在容器内拉取指定分支/标签/提交，**同时编译转发程序和配对工具**，保证两者的 whatsmeow 版本一致。首次需几分钟和 1–2 GB 内存。跨大版本更新推荐用这个。 |
| 上传二进制 | 上传自己编译的 Linux 可执行文件。 |

新版本保存在 `data/bin/`（优先于镜像内置版本），上一版本保留在 `data/bin/prev/`，可一键回滚；新版本启动失败会自动回滚。删除 `data/bin/` 即恢复镜像内置版本。

**模拟器里的 WhatsApp**：「安卓手机」页点「检查并更新到最新版」，会对比 whatsapp.com 官方最新 APK，有新版才下载并覆盖安装（聊天和登录都保留）。也可以上传自己下载的官方 APK，或在「保活与提醒」里开启「保活开机时自动更新」。

**镜像本身**（Android SDK、管理面板）：使用预编译镜像时执行 `docker compose pull && docker compose up -d`；自行构建时执行 `docker compose build --pull && docker compose up -d`。`data/` 不受影响。

## 数据目录 `/data`

| 路径 | 内容 |
| --- | --- |
| `config.yaml` | watgbridge 配置（面板生成/编辑） |
| `bridge/wawebstore.db` | WhatsApp 关联会话（whatsmeow） |
| `bridge/gobot.sqlite.db` | 转发映射数据库（会话 ↔ 话题、消息 ID） |
| `bin/` | 在线更新的 watgbridge / wapair（`prev/` 为上一版本） |
| `build/` | 源码编译的缓存（可随时删除） |
| `android/` | 模拟器 AVD 和 userdata（模拟器上的 WhatsApp 账号） |
| `apk/` | 下载/上传的 APK |
| `logs/` | 各组件日志（面板「日志」页可查看） |
| `manager.json` | 面板状态（保活设置、最后在线时间） |

备份整个 `data/` 目录即可完整迁移。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `WEB_PASSWORD` | 自动生成 | 管理面板密码 |
| `WEB_PORT` | `8080` | 面板端口 |
| `TZ` | `Asia/Shanghai` | 容器时区 |
| `EMU_RAM_MB` | `3072` | 模拟器内存 |
| `EMU_CORES` | `2` | 模拟器 CPU 核数 |
| `EMU_WIDTH` / `EMU_HEIGHT` / `EMU_DENSITY` | `720` / `1280` / `320` | 模拟器分辨率 |
| `EMU_DATA_SIZE` | `6G` | userdata 分区大小（仅首次创建时生效） |
| `EMU_EXTRA_ARGS` | 空 | 额外的 emulator 启动参数 |
| `WHATSAPP_APK_URL` | whatsapp.com 官方地址 | WhatsApp APK 下载地址 |
| `WATGBRIDGE_GITHUB` | `akshettrj/watgbridge` | 在线更新使用的 GitHub 仓库（Release 与源码） |

构建参数：`WATGBRIDGE_REF`（镜像内置 watgbridge 的分支/tag，默认 `main`）、`ANDROID_API`（默认 `34`）、`CMDLINE_TOOLS_VERSION`。

## 常见问题

**模拟器启动失败 / 状态 FATAL**：查看「日志 → 安卓模拟器」。最常见是没有 `/dev/kvm`，或宿主机内存不足。

**配对码登录失败**：默认以 Android 客户端类型 (`client_mode: android`) 关联，这样可以接收「阅后即焚」媒体。若配对码方式报错，到「转发配置 → WhatsApp → 登录客户端类型」改为「桌面/网页客户端」后重试，或用二维码 + 实体手机。

**关联设备被注销了**：说明主手机（模拟器）离线太久，见上文「关联过期后重新授权」。

**更新后重新关联提示数据库版本错误**：用「从源码编译」方式更新一次，让配对工具与转发程序版本一致。

## 项目结构

```
Dockerfile              多阶段构建：编译 watgbridge + wapair，安装 Android SDK/模拟器/noVNC
docker-compose.yml
docker/
  supervisord.conf      进程管理：manager 常驻，bridge 与 android:* 由面板按需启停
  start-emulator.sh     首次自动创建 AVD 并启动模拟器
  run-bridge.sh         启动 watgbridge（优先 /data/bin 中的更新版本）
  entrypoint.sh
manager/                管理面板 (FastAPI + 原生 JS)
  app.py                API、noVNC WebSocket 转发、保活/提醒/失效检测、在线更新
  config_schema.py      watgbridge 配置表单定义（中英文）
  static/               前端页面（i18n.js 为中英文对照）
wapair/main.go          WhatsApp 关联工具（配对码/二维码），编译进 watgbridge 源码树
```
