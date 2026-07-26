# -*- coding: utf-8 -*-
import base64, os, sys, logging, logging.handlers, yaml

# Load config from YAML
_config_path = os.path.join(os.path.dirname(__file__), 'sql.lib.yml')
with open(_config_path, 'r') as _f:
    _config = yaml.safe_load(_f)

_server = _config.get('server', {})

use_ssl = _server.get('use_ssl', True)
http_server_port = _server.get('http_server_port', 443)
default_cache_timeout_s = _server.get('default_cache_timeout_s', 15)

# Parse db_connections list
# Password for each connection is looked up from env var: <name>_token (base64-encoded)
db_connections = {}
db_credentials_error = ''

for _conn in _config.get('db_connections', []):
    _name = _conn.get('name', '')
    if not _name:
        continue
    _env_var = f'{_name}_token'
    _raw_token = os.getenv(_env_var, '')
    _entry = {
        'user': _conn.get('user', ''),
        'dsn': _conn.get('dsn', ''),
        'pwd': '',
        'error': '',
    }
    if not _raw_token:
        _entry['error'] = f'Database credentials not set: env variable {_env_var} is empty'
    else:
        try:
            _entry['pwd'] = base64.b64decode(_raw_token).decode('utf-8')
            if not _entry['pwd']:
                _entry['error'] = f'Database credentials invalid: {_env_var} decoded password is empty'
        except Exception as e:
            _entry['error'] = f'Database credentials invalid ({_env_var}): {e}'
    db_connections[_name] = _entry

# Backward compatibility: expose first connection as flat vars
_first_conn = next(iter(db_connections.values()), None)
if _first_conn:
    user = _first_conn['user']
    dsn = _first_conn['dsn']
    pwd64 = _first_conn['pwd']
    db_credentials_error = _first_conn['error']
else:
    user = ''
    dsn = ''
    pwd64 = ''
    db_credentials_error = 'No db_connections configured'

# Log critical credential errors
_errors = [c['error'] for c in db_connections.values() if c['error']]
if _errors:
    for _err in _errors:
        print(f'CRITICAL: {_err}', file=sys.stderr)
    _logger = logging.getLogger('ora2json_webserv')
    _logger.setLevel(logging.CRITICAL)
    try:
        if sys.platform.startswith('linux'):
            _logger.addHandler(logging.handlers.SysLogHandler(address='/dev/log'))
        else:
            _logger.addHandler(logging.handlers.NTEventLogHandler('ora2json_webserv'))
    except Exception:
        pass
    for _err in _errors:
        _logger.critical(_err)
