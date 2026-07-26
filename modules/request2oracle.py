"""
Oracle2JSON module
Kotov E.
v0.4
2026-07-24
python 3
"""

## -*- coding: utf-8 -*-
import oracledb, json, os, queue, time
import threading as th
from datetime import datetime, timedelta
from config.config import *
from modules.tech_func import *



##################################################################################
def initialize_oracle_client():
    """Enable python-oracledb Thick mode when requested by the environment."""
    mode = os.getenv('ORACLE_USE_THICK_MODE', '').strip().lower()
    true_values = {'1', 'true', 'yes', 'on'}
    false_values = {'', '0', 'false', 'no', 'off'}

    if mode in false_values:
        return
    if mode not in true_values:
        raise RuntimeError(
            'Invalid ORACLE_USE_THICK_MODE value. '
            'Use true/false, yes/no, on/off, or 1/0.'
        )

    client_lib_dir = os.getenv('ORACLE_CLIENT_LIB_DIR', '').strip()
    try:
        if client_lib_dir:
            oracledb.init_oracle_client(lib_dir=client_lib_dir)
        else:
            oracledb.init_oracle_client()
    except Exception as exc:
        location = client_lib_dir or 'the operating system library search path'
        raise RuntimeError(
            'Failed to enable python-oracledb Thick mode using '
            f'{location}. Install a compatible Oracle Instant Client and check '
            'ORACLE_CLIENT_LIB_DIR/LD_LIBRARY_PATH. Original error: '
            f'{exc}'
        ) from exc

    if oracledb.is_thin_mode():
        raise RuntimeError(
            'ORACLE_USE_THICK_MODE is enabled, but python-oracledb is still '
            'running in Thin mode.'
        )


initialize_oracle_client()


##################################################################################

def get_connection_params(conn_name=None):
    if conn_name and conn_name in db_connections:
        conn = db_connections[conn_name]
    else:
        conn = next(iter(db_connections.values()), None)
    if not conn:
        return None, None, None, 'No db_connections configured'
    return conn['user'], conn['pwd'], conn['dsn'], conn['error']


def exec_sql_cmd(sql, conn_name=None):

    result_rows, f_result = [], False
    db_user, db_pwd, db_dsn, conn_error = get_connection_params(conn_name)
    if conn_error:
        add_to_log(f'ERROR.\t{conn_error}')
        return False, {'ERROR': conn_error}
    try:
        with oracledb.connect(user=db_user, password=db_pwd, dsn=db_dsn, tcp_connect_timeout=5) as con:
            cur = con.cursor()
            cur.execute(sql)
            for row in cur.fetchall():
                res = {}
                index = -1
                for val in row:
                    index += 1
                    val = str(val) if type(val) not in (int, str) else val
                    res[cur.description[index][0]] = val
                result_rows.append(res)
        f_result = True
    except Exception as e:
        add_to_log(print_exception(e))
        result_rows = {'ERROR': str(e)}
    return f_result, result_rows


def get_sql_data(cmd):
    add_to_log(f'INFO.\tStart SQL request: {cmd}')
    begin_time = datetime.now()
    sql_list = get_configs(os.path.join('config', 'sql.lib.yml'))
    sql_entry = sql_list.get(cmd)
    if not sql_entry:
        add_to_log(f'WARNING.\tUnknown SQL request: {cmd}')
        return {'ERROR': 'Unknown SQL.'}, (datetime.now() - begin_time).total_seconds()

    eSQL = sql_entry.get('sql')
    if not isinstance(eSQL, str) or not eSQL.strip():
        add_to_log(f'ERROR.\tSQL request "{cmd}" is not configured or SQL file could not be loaded.')
        return {'ERROR': 'SQL is not configured or SQL file could not be loaded.'}, \
            (datetime.now() - begin_time).total_seconds()

    conn_name = sql_entry.get('connection')
    cache_timeout_s = sql_entry.get('cache_timeout_s', default_cache_timeout_s)
    # check results in cache
    f_data = get_sql_cache(cmd, cache_timeout_s)
    if len(f_data) > 0:
        f_result = True
    else:
        # get from DB if cache is empty
        f_result, f_data = exec_sql_cmd(eSQL, conn_name)
        if f_result and len(f_data) > 0:
            set_sql_cache(cmd, f_data)
    add_to_log(f'INFO.\tFinish SQL request: {cmd}')
    duration_s = (datetime.now() - begin_time).total_seconds()
    return f_data, duration_s


def set_sql_cache(cmd: str, sql_data: list):
    set_config(filename=os.path.join('cache', cmd + '.json'),
               conf={'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 'data': sql_data})


def get_sql_cache(cmd: str, cache_timeout_s: int):
    cache_data = get_configs(filename=os.path.join('cache', cmd + '.json'), fast_mode=True)
    if (datetime.strptime(cache_data.get('timestamp', '1999-01-01T00:00:00'), '%Y-%m-%dT%H:%M:%S')) \
            > (datetime.now() - timedelta(seconds=cache_timeout_s)):     # check cache lifetime
        add_to_log(f'INFO.\tReturn cache for SQL: {cmd}')
        return cache_data.get('data', [])
    else:
        return []


##################################################################################
if __name__ == '__main__':
    from sys import argv

    if len(argv) == 2:
        add_to_log(f'INFO.\tRun args: {argv[1]}')
        data, duration = get_sql_data(argv[1])
        add_to_log(f'INFO.\tRequest return data length: {len(data)}.')
        exit(0) if len(data) > 0 else exit(1)
    else:
        add_to_log('WARNING.\tArguments must be 1. Usage: \"script_name.py sql_cmf_name\"')
