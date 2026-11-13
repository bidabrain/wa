# syntax=docker/dockerfile:1
#
# WA-TG Bridge：安卓模拟器(官方 WhatsApp) + watgbridge + 图形化管理面板，单镜像。
#
#   docker build -t wa-tg-bridge .
#
# 可选构建参数：
#   WATGBRIDGE_REF   watgbridge 的分支或 tag（默认 main）
#   ANDROID_API      安卓系统镜像 API 级别（默认 34）
#   SYSTEM_IMAGE     sdkmanager 系统镜像包名

ARG WATGBRIDGE_REPO=https://github.com/akshettrj/watgbridge.git
ARG WATGBRIDGE_REF=main

# ------------------------------------------------------------------ 1. 编译 watgbridge 与 wapair
FROM golang:1.26-bookworm AS bridge-build
ARG WATGBRIDGE_REPO
ARG WATGBRIDGE_REF
ENV CGO_ENABLED=1 GOTOOLCHAIN=auto
RUN apt-get update \
 && apt-get install -y --no-install-recommends git build-essential \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch "${WATGBRIDGE_REF}" "${WATGBRIDGE_REPO}" watgbridge
WORKDIR /src/watgbridge
RUN --mount=type=cache,target=/go/pkg/mod go mod download
# wapair 放进 watgbridge 源码树编译，保证与 watgbridge 使用同一版本的 whatsmeow 和配置结构
COPY wapair/main.go ./cmd/wapair/main.go
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    mkdir -p /out \
 && go build -trimpath -ldflags "-s -w" -o /out/watgbridge . \
 && go build -trimpath -ldflags "-s -w" -o /out/wapair ./cmd/wapair \
 && printf '{"source":"image","ref":"%s","commit":"%s","version":"%s"}\n' \
      "${WATGBRIDGE_REF}" "$(git rev-parse --short HEAD)" "$(cat state/version.txt 2>/dev/null | tr -d '\n')" > /out/version.json

# ------------------------------------------------------------------ 2. 运行环境
FROM ubuntu:24.04

ARG CMDLINE_TOOLS_VERSION=13114758
ARG ANDROID_API=34
ARG SYSTEM_IMAGE="system-images;android-${ANDROID_API};google_apis;x86_64"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    TZ=Asia/Shanghai \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_USER_HOME=/data/android \
    ANDROID_EMULATOR_HOME=/data/android \
    ANDROID_AVD_HOME=/data/android/avd \
    SYSTEM_IMAGE=${SYSTEM_IMAGE} \
    DISPLAY=:1 \
    SCREEN_GEOMETRY=760x1300x24 \
    VNC_PORT=5900 \
    WEB_PORT=8080 \
    DATA_DIR=/data \
    PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/emulator:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip tzdata git sqlite3 gcc g++ libc6-dev \
      supervisor python3 python3-venv \
      ffmpeg webp imagemagick \
      openjdk-17-jre-headless \
      xvfb x11vnc novnc \
      libpulse0 libnss3 libxcomposite1 libxcursor1 libxi6 libxtst6 libasound2t64 \
      libgl1 libegl1 libgbm1 libdrm2 libxkbfile1 libxdamage1 libxrandr2 libdbus-1-3 \
      libfontconfig1 libx11-xcb1 libxkbcommon0 libxkbcommon-x11-0 \
      libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
      libxcb-shape0 libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxcb-cursor0 libxcb-util1 \
 && rm -rf /var/lib/apt/lists/*

# Android SDK：命令行工具、platform-tools(adb)、模拟器、x86_64 系统镜像
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools \
 && curl -fsSL -o /tmp/clt.zip "https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip" \
 && unzip -q /tmp/clt.zip -d ${ANDROID_HOME}/cmdline-tools \
 && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
 && rm /tmp/clt.zip \
 && (yes | sdkmanager --licenses > /dev/null || true) \
 && sdkmanager --install "platform-tools" "emulator" "${SYSTEM_IMAGE}" > /dev/null \
 && rm -rf /root/.android /tmp/*

# 管理面板
COPY manager/requirements.txt /opt/manager/requirements.txt
RUN python3 -m venv /opt/manager/venv \
 && /opt/manager/venv/bin/pip install --no-cache-dir -r /opt/manager/requirements.txt
COPY manager/ /opt/manager/

# Go 编译环境：用于在管理面板里「从源码编译」更新 watgbridge，无需重建镜像
COPY --from=bridge-build /usr/local/go /usr/local/go
ENV GOTOOLCHAIN=auto GO_BIN=/usr/local/go/bin/go

# 镜像内置版本的 watgbridge / wapair；在线更新后的版本放在 /data/bin 并优先使用
COPY --from=bridge-build /out/watgbridge /out/wapair /out/version.json /opt/watgbridge/
COPY wapair/main.go /opt/watgbridge/src/wapair/main.go
COPY docker/supervisord.conf /etc/supervisor/wa.conf
COPY docker/start-emulator.sh docker/entrypoint.sh docker/run-bridge.sh /opt/scripts/
RUN sed -i 's/\r$//' /opt/scripts/*.sh /etc/supervisor/wa.conf \
 && chmod +x /opt/scripts/*.sh /opt/watgbridge/watgbridge /opt/watgbridge/wapair

VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD curl -fsS "http://127.0.0.1:${WEB_PORT}/healthz" || exit 1
ENTRYPOINT ["/opt/scripts/entrypoint.sh"]
