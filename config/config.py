# -*- coding: utf-8 -*-
import base64, os

use_ssl = False
http_server_port = 443
default_cache_timeout_s = 15
dsn = 'oracle-db.host.com/db-name'
user = 'db-user'
pwd64 = base64.b64decode(os.getenv('db-pwd', '')).decode('utf-8')   # in file ~/.bashrc


