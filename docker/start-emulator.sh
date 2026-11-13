#!/usr/bin/env bash
# 启动安卓模拟器（由 supervisord 调用）。首次运行时自动创建 AVD，数据保存在 /data/android。
set -euo pipefail

AVD_NAME="${AVD_NAME:-wa}"
AVD_DIR="${ANDROID_AVD_HOME}/${AVD_NAME}.avd"
EMU="${ANDROID_HOME}/emulator/emulator"

log() { echo "[start-emulator] $(date '+%F %T') $*"; }

if [[ ! -r /dev/kvm || ! -w /dev/kvm ]]; then
  log "错误：/dev/kvm 不可用。请在宿主机启用硬件虚拟化，并用 --device /dev/kvm 运行容器。"
  exit 1
fi

mkdir -p "${ANDROID_AVD_HOME}"

if [[ ! -f "${AVD_DIR}/config.ini" ]]; then
  log "首次运行，创建 AVD ${AVD_NAME}（${SYSTEM_IMAGE}）"
  echo "no" | avdmanager create avd --force -n "${AVD_NAME}" -k "${SYSTEM_IMAGE}" -d pixel -p "${AVD_DIR}"
fi

# 每次启动都校正关键配置（便于升级镜像后调整参数）
set_ini() {
  local key="$1" value="$2" file="${AVD_DIR}/config.ini"
  if grep -q "^${key}[ ]*=" "$file"; then
    sed -i "s|^${key}[ ]*=.*|${key}=${value}|" "$file"
  else
    echo "${key}=${value}" >> "$file"
  fi
}
set_ini hw.lcd.width "${EMU_WIDTH:-720}"
set_ini hw.lcd.height "${EMU_HEIGHT:-1280}"
set_ini hw.lcd.density "${EMU_DENSITY:-320}"
set_ini hw.ramSize "${EMU_RAM_MB:-3072}"
set_ini hw.cpu.ncore "${EMU_CORES:-2}"
set_ini disk.dataPartition.size "${EMU_DATA_SIZE:-6G}"
set_ini hw.keyboard yes
set_ini hw.gpu.enabled yes
set_ini hw.gpu.mode swiftshader_indirect
set_ini hw.audioInput no
set_ini hw.audioOutput no
set_ini hw.camera.back none
set_ini hw.camera.front none
set_ini showDeviceFrame no
set_ini skin.dynamic yes
set_ini fastboot.forceColdBoot yes

# 清理上次异常退出留下的锁
rm -f "${AVD_DIR}"/*.lock 2>/dev/null || true
rm -rf "${AVD_DIR}"/*.lock.d 2>/dev/null || true

# 等待 X 服务器
for _ in $(seq 1 30); do
  [[ -S /tmp/.X11-unix/X${DISPLAY#:} ]] && break
  sleep 1
done

log "启动模拟器"
exec "${EMU}" -avd "${AVD_NAME}" \
  -no-audio -no-boot-anim -no-snapshot -no-metrics \
  -gpu swiftshader_indirect -accel on \
  -camera-back none -camera-front none \
  -netdelay none -netspeed full \
  ${EMU_EXTRA_ARGS:-}
