#!/usr/bin/env bash
# One-time Unraid installer for a persistent Remote Desktop Commander device agent.
# Device auth tokens are copied privately on Unraid, NEVER committed to GitHub.
set -euo pipefail
if [[ "$(id -u)" != 0 || ! -f /boot/config/go || ! -d /mnt/user/appdata ]]; then
  echo "Execute como root no Unraid com o array montado." >&2
  exit 1
fi

APP=/mnt/user/appdata/remote-desktop-commander
AUTH="$APP/device"
ORIGINAL=/root/.desktop-commander-device
LAUNCHER=/boot/config/custom/remote-desktop-commander.sh
mkdir -p "$AUTH" /boot/config/custom
chmod 700 "$APP" "$AUTH"
if [[ -s "$ORIGINAL/device.json" && ! -L "$ORIGINAL" && ! -s "$AUTH/device.json" ]]; then
  cp -p "$ORIGINAL/device.json" "$AUTH/device.json"
fi
if [[ ! -s "$AUTH/device.json" ]]; then
  echo "Autorização anterior não encontrada." >&2
  echo "Execute: npx @wonderwhy-er/desktop-commander@latest remote" >&2
  echo "Depois de Device ready, Ctrl+C e repita este instalador." >&2
  exit 2
fi
chmod 600 "$AUTH/device.json"
if [[ -d "$ORIGINAL" && ! -L "$ORIGINAL" ]]; then
  mv "$ORIGINAL" "$ORIGINAL.before-unraid-service.$(date +%Y%m%d-%H%M%S)"
fi
ln -sfn "$AUTH" "$ORIGINAL"

cat > "$LAUNCHER" <<'AGENT'
#!/usr/bin/env bash
set -u
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
APP=/mnt/user/appdata/remote-desktop-commander
AUTH="$APP/device"
PID=/var/run/remote-desktop-commander.pid
LOG="$APP/agent.log"
SELF=/boot/config/custom/remote-desktop-commander.sh
case "$1" in
  start)
    [[ -s "$AUTH/device.json" ]] || { echo "Credencial não encontrada." >&2; exit 1; }
    mkdir -p "$APP"
    chmod 700 "$APP" "$AUTH"
    # /root lives in Unraid RAM; restore the credential symlink after reboot.
    if [[ -d /root/.desktop-commander-device && ! -L /root/.desktop-commander-device ]]; then
      mv /root/.desktop-commander-device "/root/.desktop-commander-device.before-service.$(date +%s)"
    fi
    ln -sfn "$AUTH" /root/.desktop-commander-device
    touch "$LOG"
    chmod 600 "$LOG"
    if [[ -s "$PID" ]] && kill -0 "$(cat "$PID")" 2>/dev/null; then
      echo "Agente já iniciado (PID $(cat "$PID"))."
      exit 0
    fi
    nohup setsid /bin/bash "$SELF" supervise </dev/null >> "$LOG" 2>&1 &
    sleep 2
    /bin/bash "$SELF" status
    ;;
  supervise)
    exec 9>/var/run/remote-desktop-commander.lock
    /usr/bin/flock -n 9 || exit 0
    echo "$$" > "$PID"
    trap 'rm -f "$PID"' EXIT
    echo "$(date -Is) Supervisor iniciado"
    while true; do
      if [[ ! -s "$AUTH/device.json" ]]; then
        echo "$(date -Is) Sem credencial; aguardo 30s"
        sleep 30
        continue
      fi
      if ! command -v npx >/dev/null 2>&1; then
        echo "$(date -Is) Sem Node.js/npx; aguardo 30s"
        sleep 30
        continue
      fi
      echo "$(date -Is) Iniciando agente..."
      npx --yes @wonderwhy-er/desktop-commander@0.2.52 remote
      result=$?
      echo "$(date -Is) Agente saiu ($result); reinicio em 15s"
      sleep 15
    done
    ;;
  status)
    if [[ -s "$PID" ]] && kill -0 "$(cat "$PID")" 2>/dev/null; then
      echo "Supervisor ativo (PID $(cat "$PID"))."
    else
      echo "Supervisor inativo."
      exit 1
    fi
    ;;
  stop)
    if [[ -s "$PID" ]]; then
      agent_pid="$(cat "$PID")"
      kill -TERM -- "-$agent_pid" 2>/dev/null || kill -TERM "$agent_pid" 2>/dev/null || true
      echo "Sinal de parada enviado."
    else
      echo "Agente não iniciado."
    fi
    ;;
  logs) tail -n 40 "$LOG" ;;
  *) echo "Uso: $SELF {start|status|stop|logs}" >&2; exit 2 ;;
esac
AGENT
chmod 700 "$LAUNCHER"

# Unraid retains /boot/config/go through reboot; wait until the array is ready.
if ! grep -Fq REMOTE_DESKTOP_COMMANDER_AUTOSTART /boot/config/go; then
  cp -p /boot/config/go "/boot/config/go.backup-rdc.$(date +%Y%m%d-%H%M%S)"
  cat >> /boot/config/go <<'BOOT'

# REMOTE_DESKTOP_COMMANDER_AUTOSTART
(
  until mountpoint -q /mnt/user; do sleep 15; done
  /bin/bash /boot/config/custom/remote-desktop-commander.sh start
) >/dev/null 2>&1 &
BOOT
fi

/bin/bash "$LAUNCHER" start
echo "Instalado: pode fechar o SSH."
echo "Status: bash $LAUNCHER status"
echo "Logs:   bash $LAUNCHER logs"
echo "Parar:  bash $LAUNCHER stop"
echo "ATENCAO: agente persistente com permissões de root. Proteja a conta."
