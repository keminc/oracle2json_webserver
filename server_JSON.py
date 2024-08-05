"""
Http Server backend
Kotov E.
v0.1
python 3
"""
import ssl
# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import parse
from modules.request2oracle import *
from modules.tech_func import *
from config.config import *
from datetime import datetime


# https://pymotw.com/3/http.server/  - very good example
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
    def log_http(self):
        parsed_path = parse.urlparse(self.path)
        # message_parts = [
        #     'CLIENT VALUES:',
        #     ' client_address={} ({})'.format(
        #         self.client_address,
        #         self.address_string()),
        #     ' command={}'.format(self.command),
        #     ' path={}'.format(self.path),
        #     ' real path={}'.format(parsed_path.path),
        #     ' query={}'.format(parsed_path.query),
        #     ' request_version={}'.format(self.request_version),
        #     '',
        #     'SERVER VALUES:',
        #     ' server_version={}'.format(self.server_version),
        #     ' sys_version={}'.format(self.sys_version),
        #     ' protocol_version={}'.format(self.protocol_version),
        #     '',
        #     'HEADERS RECEIVED:',
        # ]
        message_parts = f'IP: {self.client_address}. Command: {self.command}. Query: {parsed_path.query}'
        for name, value in sorted(self.headers.items()):
            message_parts = message_parts + '. %s=%s' % (name, value.rstrip())
        add_to_log('DEBUG.\tConnected client.\t' + message_parts)

    def log_message(self, lformat, *args):
        message = lformat % args
        add_to_log('DEBUG.\t' + "%s - - [%s] %s\n" % (self.address_string(),
                                                      self.log_date_time_string(),
                                                      message.translate(self._control_char_table)))

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_HEAD(self):
        self._set_headers()

    # GET sends back a Hello world message
    def do_GET(self):
        # Get client data
        # self.log_http()
        self._set_headers()
        if self.path == '/favicon.ico':
            # self.send_response(200)
            # self.send_header('Content-Type', 'image/x-icon')
            # self.send_header('Content-Length', '0')
            # self.end_headers()
            return
        elif self.path == '/stat':
            self.wfile.write(json.dumps(service_stat).encode('utf-8'))
            return
        elif len(self.path) > 3:
            req = self.path.replace('/', '')
            rdata, rduration = get_sql_data(req)
            set_stat(req, rduration)
            self.wfile.write(json.dumps(rdata).encode('utf-8'))
        else:
            self.wfile.write(json.dumps({'message': 'Select valid path.'}).encode('utf-8'))


def run(handler_class=Server, port=http_server_port):
    server_address = ('', port)
    try:
        httpd = ThreadingHTTPServer(server_address, handler_class)

        if use_ssl:
            prefix = 'https'
            sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            sslctx.check_hostname = False  # If set to True, only the hostname that matches the certificate will be accepted
            sslctx.hostname_checks_common_name = False
            sslctx.load_cert_chain(certfile=os.path.join('ssl', 'monitoring_api.pem'), keyfile=os.path.join('ssl', 'monitoring_api.privkey.pem'))
            httpd.socket = sslctx.wrap_socket(httpd.socket, server_side=True)
        else:
            prefix='http'

        sa = httpd.socket.getsockname()
        add_to_log(f"INFO.\tStart serving HTTP on {prefix}://" + ('127.0.0.1' if sa[0] == '0.0.0.0' else sa[0]) + ":" + str(sa[1]) + "/test")
        service_stat['staring'] = str(datetime.now())
        httpd.serve_forever()
    except Exception as e:
        print('Error: ' + str(e))
    finally:
        add_to_log("INFO.\tStop serving HTTP...")


# MAIN
if __name__ == "__main__":
    service_stat = {}
    run()
