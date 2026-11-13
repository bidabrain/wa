#!/usr/bin/env bash
# 启动 watgbridge：优先使用在线更新的版本 /data/bin/watgbridge，否则使用镜像内置版本。
BIN=/data/bin/watgbridge
if [[ ! -x "$BIN" ]]; then
  BIN=/opt/watgbridge/watgbridge
fi
echo "[run-bridge] $(date '+%F %T') using $BIN"
exec "$BIN" /data/config.yaml
