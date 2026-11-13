#!/usr/bin/env bash
set -euo pipefail

mkdir -p /data/logs /data/bridge /data/apk /data/bin /data/build "${ANDROID_AVD_HOME}" /run

if [[ ! -e /dev/kvm ]]; then
  echo "[entrypoint] 提示：未检测到 /dev/kvm，安卓模拟器将不可用（转发服务仍可正常运行）。"
fi

exec /usr/bin/supervisord -n -c /etc/supervisor/wa.conf
