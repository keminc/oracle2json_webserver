"""
Http Server backend
Kotov E.
v0.3
python 3
"""
import os
import ssl
import sys
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import parse
import config.config as app_config
from config.config import *
from modules.request2oracle import *
from modules.tech_func import *
from modules.json_filter import apply_filters
from modules.json_time_filter import apply_time_filter
from datetime import datetime




def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def readfile_json(file):
    try:
        with open(file) as json_file:
            return json.load(json_file)
    except Exception as e:
        return {'error': str(e)}


def set_stat(req, duration_s: int):
    if req not in service_stat:
        service_stat[req] = {'count': 0, 'duration_s': 0}

    service_stat[req]['count'] += 1
    service_stat[req]['duration_s'] = round(service_stat[req]['duration_s'] + duration_s, 2)


class Server(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'  # keep-alive: reuse one TCP connection for many requests

    def log_http(self):
        parsed_path = parse.urlparse(self.path)
        message_parts = f'IP: {self.client_address}. Command: {self.command}. Query: {parsed_path.query}'
        for name, value in sorted(self.headers.items()):
            message_parts = message_parts + '. %s=%s' % (name, value.rstrip())
        add_to_log('DEBUG.\tConnected client.\t' + message_parts)

    def log_message(self, lformat, *args):
        message = lformat % args
        add_to_log('DEBUG.\t' + "%s - - [%s] %s\n" % (self.address_string(),
                                                      self.log_date_time_string(),
                                                      message.translate(self._control_char_table)))

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        parsed_path = parse.urlparse(self.path)
        request_path = parsed_path.path

        if request_path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return

        if request_path == '/health':
            self._send_json({
                'status': 'ok',
                'db_credentials': 'invalid' if app_config.db_credentials_error else 'ok'
            })
            return

        if request_path in ('/status', '/stat'):
            self._serve_status()
            return

        if request_path == '/':
            self._serve_help()
            return

        if app_config.db_credentials_error:
            self._send_json({'error': app_config.db_credentials_error, 'status': 'service_unavailable'}, 503)
            return

        elif len(request_path) > 3:
            req = parse.unquote(request_path.strip('/'))
            rdata, rduration = get_sql_data(req)
            set_stat(req, rduration)
            query_string = parsed_path.query
            if query_string:
                rdata = apply_time_filter(rdata, query_string)
                rdata = apply_filters(rdata, query_string)
            self._send_json(rdata)
        else:
            self._send_json({'message': 'Select valid path.'})


    def _serve_status(self):
        overall_status = 'ok'

        if app_config.db_credentials_error:
            overall_status = 'degraded'
            database_status = {
                'status': 'service_unavailable',
                'error': app_config.db_credentials_error
            }
        else:
            try:
                data, duration_s = get_sql_data('status')
                set_stat('status', duration_s)
                db_ok = not (isinstance(data, dict) and 'ERROR' in data)
                if not db_ok:
                    overall_status = 'degraded'
                database_status = {
                    'status': 'ok' if db_ok else 'error',
                    'duration_s': duration_s,
                    'data': data
                }
            except Exception as e:
                overall_status = 'degraded'
                database_status = {
                    'status': 'internal_error',
                    'error': str(e)
                }

        self._send_json({
            'status': overall_status,
            'service': service_stat,
            'database': database_status
        })

    def _serve_help(self):
        try:
            from modules.tech_func import get_configs
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'sql.lib.yml')
            cfg = get_configs(config_path, fast_mode=True)
            skip_keys = ('server', 'db_connections')
            endpoints = [k for k in cfg if k not in skip_keys]
            endpoints_html = ''.join(f'<li><a href="/{e}">{e}</a></li>' for e in endpoints)

            help_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'help.html')
            with open(help_path, 'r', encoding='utf-8') as f:
                html = f.read()
            html = html.replace('{{ENDPOINTS}}', endpoints_html)

            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._send_json({'error': f'Failed to load help page: {e}'}, 500)


def run(handler_class=Server, port=None):
    if port is None:
        port = app_config.http_server_port

    server_address = ('', port)
    httpd = None
    try:
        httpd = ThreadingHTTPServer(server_address, handler_class)

        if app_config.use_ssl:
            prefix = 'https'
            sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            sslctx.check_hostname = False
            sslctx.hostname_checks_common_name = False
            sslctx.load_cert_chain(certfile=os.path.join('ssl', 'monitoring_api.pem'), keyfile=os.path.join('ssl', 'monitoring_api.privkey.pem'))
            httpd.socket = sslctx.wrap_socket(httpd.socket, server_side=True)
        else:
            prefix = 'http'

        def shutdown_handler(signum, frame):
            add_to_log(f"INFO.\tReceived signal {signum}, shutting down...")
            threading.Thread(target=httpd.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        sa = httpd.socket.getsockname()
        add_to_log(f"INFO.\tStart serving HTTP on {prefix}://" + ('127.0.0.1' if sa[0] == '0.0.0.0' else sa[0]) + ":" + str(sa[1]) + "/test")
        service_stat['starting'] = str(datetime.now())
        httpd.serve_forever()
    except Exception as e:
        print('Error: ' + str(e))
    finally:
        if httpd:
            httpd.server_close()
        add_to_log("INFO.\tStop serving HTTP...")


if __name__ == "__main__":
    ensure_dir('logs')
    ensure_dir('cache')

    if app_config.db_credentials_error:
        add_to_log(f'CRITICAL.\t{app_config.db_credentials_error}. Service will respond 503 on all endpoints.')

    service_stat = {}
    run()
