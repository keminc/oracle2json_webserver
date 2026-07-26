#!/bin/bash

#Autorun
# cd /etc/init.d/; ln -s /opt/scripts/ora2json_webserv/run.sh

# C R O N 
# m         h       dom    mon      dow     command
# 0,30      *      *       *       *       cd /opt/scripts/ora2json_webserv && ./run.sh restart


###########################################################################################
# F U N C T I O N S
###########################################################################################

APP_DIR="${APP_DIR:-/opt/scripts/ora2json_webserv}"
if [[ ! -d "$APP_DIR" ]]; then
  APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

function log() {
  mkdir -p logs
  echo "$(date '+%F %T') $*" | tee -a logs/server.log
}

function run_cmd() {
  log "+ $*"
  "$@" 2>&1 | tee -a logs/server.log
  return "${PIPESTATUS[0]}"
}

function source_env_file() {
  local env_file="$1"
  [[ -r "$env_file" ]] || return 0
  # Env files may print banners or contain interactive-only commands.
  # Keep restart output focused and tolerate non-critical init failures.
  . "$env_file" >/dev/null 2>&1 || true
}

function get_token_names_from_config() {
  python3 -c "
import yaml, os
cfg_path = os.path.join('config', 'sql.lib.yml')
with open(cfg_path) as f:
    cfg = yaml.safe_load(f)
for conn in cfg.get('db_connections', []):
    name = conn.get('name', '')
    if name:
        print(name + '_token')
" 2>/dev/null
}

function load_runtime_env() {
  log "Environment: loading runtime variables..."

  local token_vars
  token_vars="$(get_token_names_from_config)"
  if [[ -z "$token_vars" ]]; then
    log "WARNING: no db_connections found in config."
    return
  fi

  local need_source=false
  for var in $token_vars; do
    if [[ -z "${!var:-}" ]]; then
      need_source=true
      break
    fi
  done

  local source_label=""
  if [[ "$need_source" == "true" ]]; then
    source_env_file /etc/profile
    source_env_file /root/.bash_profile
    source_env_file /root/.bash_login
    source_env_file /root/.profile
    source_env_file /root/.bashrc
    source_label="root shell init files"

    if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
      local sudo_home
      sudo_home="$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6)"
      if [[ -n "$sudo_home" ]]; then
        source_env_file "$sudo_home/.bash_profile"
        source_env_file "$sudo_home/.bash_login"
        source_env_file "$sudo_home/.profile"
        source_env_file "$sudo_home/.bashrc"
      fi
      source_label="${SUDO_USER} shell init files"
    fi

    # Fallback: eval export lines directly from init files
    for var in $token_vars; do
      if [[ -z "${!var:-}" ]]; then
        local export_line
        export_line="$(grep -h "export ${var}=" /root/.bashrc /root/.bash_profile /root/.profile /etc/profile 2>/dev/null | tail -n 1)"
        if [[ -n "$export_line" ]]; then
          eval "$export_line"
          source_label="parsed from init files"
        fi
      fi
    done

    # Last resort: interactive shell
    for var in $token_vars; do
      if [[ -z "${!var:-}" ]]; then
        local fetched
        fetched="$(bash -ic "printf '__TOKEN__%s\n' \"\$${var}\"" 2>/dev/null | sed -n 's/^__TOKEN__//p' | tail -n 1)"
        if [[ -n "$fetched" ]]; then
          export "$var=$fetched"
          source_label="interactive shell"
        fi
      fi
    done
  fi

  local all_found=true
  for var in $token_vars; do
    if [[ -n "${!var:-}" ]]; then
      export "$var"
      log "Environment: $var found${source_label:+ ($source_label)} and exported."
    else
      log "WARNING: $var not found. Endpoints using this connection will return HTTP 503."
      all_found=false
    fi
  done

  if [[ "$all_found" == "true" ]]; then
    log "Environment: all DB tokens loaded successfully."
  fi
}

function update_from_git() {
  log "Git: checking for updates..."
  log "Git: repository $(pwd)"
  log "Git: remote $(git remote get-url origin 2>/dev/null || echo 'not configured')"
  local before_head
  local after_head
  before_head="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
  log "Git: current version $before_head on branch $(git branch --show-current 2>/dev/null || echo 'unknown')"

  run_cmd git fetch origin || return 1

  local target
  target="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
  if [[ -z "$target" ]]; then
    if git rev-parse --verify --quiet origin/main >/dev/null; then
      target="origin/main"
    else
      target="origin/master"
    fi
  fi

  log "Git: syncing with $target"
  run_cmd git reset --hard "$target" || return 1
  after_head="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
  if [[ "$before_head" == "$after_head" ]]; then
    log "Git: already up to date ($after_head)."
  else
    log "Git: updated successfully ($before_head -> $after_head)."
  fi
  run_cmd git status --short --untracked-files=no
}

function refresh_runtime_state() {
  config_port="$(python3 -c "import config.config as cfg; print(cfg.http_server_port)" 2>/dev/null)"
  if [[ -z "$config_port" ]]; then
    config_port="$(python3 -c "import yaml; print(yaml.safe_load(open('config/sql.lib.yml')).get('server',{}).get('http_server_port',443))" 2>/dev/null)"
  fi

  service_name="$(netstat -apn 2>/dev/null | egrep "tcp.*:${config_port}.*0.0.0.0.*LISTEN.*python" | awk '{print $7}' | head -n 1)"
  service_pid="$(echo "$service_name" | cut -d'/' -f1)"

  if [[ -z "$service_pid" ]]; then
    service_pid="$(pgrep -f 'python3? .*server_JSON.py|python .*server_JSON.py' 2>/dev/null | head -n 1)"
    [[ -n "$service_pid" ]] && service_name="${service_pid}/python"
  fi
}

function status() {
  refresh_runtime_state
  log "Service: checking port ${config_port:-unknown}..."
	[[ ${#service_name} -gt 0 ]] && log "Service: running ($service_name)." || log "Service: not running."
}

function check_credentials() {
  credentials_error=`python3 -c "import config.config as cfg; print(cfg.db_credentials_error)" 2>/dev/null`
  if [[ ${#credentials_error} -gt 0 ]]; then
    echo "CRITICAL: ${credentials_error}" | tee -a logs/server.log
  fi
}


function fstop() {
  log "Service: stopping..."
  refresh_runtime_state
	if [[ -n "$service_pid" ]]; then
	  log "Service: stopping process $service_name..."
	  kill "$service_pid" >/dev/null && log "Service: process stopped." && service_name="" || log "ERROR: failed to stop service process."
	else
	  log "Service: no running process found."
	fi
	# check service
	local check_pid
	check_pid=`ps -ef |grep service_check.sh |grep -v grep | awk '{print $2}'`
  if [[ -n "$check_pid" ]]; then
    log "Watchdog: stopping process $check_pid..."
    kill -9 $check_pid >/dev/null && log "Watchdog: stopped." || log "ERROR: failed to stop watchdog."
  else
    log "Watchdog: no running process found."
  fi
}

function fstart() {
  log "Service: starting..."
  load_runtime_env
  refresh_runtime_state
	[[ ${#service_name} -gt 0 ]] && log "Service: already running on port $config_port ($service_name)." && exit 1
	check_credentials
	log "Service: launching HTTP server..."
	python3 server_JSON.py  >> logs/server.log 2>&1  &
	sleep 2
	refresh_runtime_state
	if 	[[ ${#service_name} -gt 0 ]]; then
	  log "Service: started successfully ($service_name)."
	  log "Watchdog: starting..."
	  bash service_check.sh >> logs/server.log 2>&1 &
	  log "Restart complete."
	else
	  log "ERROR: service did not start. Check logs/server.log for details."
	  return 1
	fi


}






###########################################################################################
# M A I N 
###########################################################################################

cd "$APP_DIR" || exit 1
mkdir -p logs cache
refresh_runtime_state


if [[ "$1" ==  "restart" ]]; then
	update_from_git || exit 1
	refresh_runtime_state
	fstop
	refresh_runtime_state
	fstart
elif [[ "$1" ==  "stop" ]]; then
	fstop
elif [[ "$1" ==  "start" ]]; then
	fstart
elif [[ "$1" ==  "status" ]]; then
	status
else
  echo -e "# Usage: run.sh stop|start|restart|status\n"
	status
fi
