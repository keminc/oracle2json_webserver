# -*- coding: utf-8 -*-
import base64, os

# HTTPS configuration block: toggles TLS for the HTTP server and port binding.
use_ssl = False
http_server_port = 443

# Caching configuration block: defines default TTL for cached SQL responses.
default_cache_timeout_s = 15

# Oracle connection configuration block: DSN, credentials and client mode toggles.
dsn = 'oracle-db.host.com/db-name'
user = 'db-user'
pwd64 = base64.b64decode(os.getenv('db-pwd', '')).decode('utf-8')   # in file ~/.bashrc

# Oracle thick client configuration block: optional Instant Client usage to avoid
# DPY-3015 errors when the database password verifier is unsupported in thin mode.
use_thick_mode = os.getenv('ORACLE_USE_THICK_MODE', 'false').lower() == 'true'
oracle_client_lib_dir = os.getenv('ORACLE_CLIENT_LIB_DIR', '')


