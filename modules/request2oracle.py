"""
Oracle2JSON module
Kotov E.
v0.1
python 3
"""

## -*- coding: utf-8 -*-
import oracledb, json, os, datetime, queue, time
import threading as th
import config
from modules.tech_func import *
from config.config import *


# Oracle client initialization state: prevents repeated init calls in multithreaded usage.
_ORACLE_CLIENT_INITIALIZED = False


def init_oracle_client_if_needed():
    """Initialize Oracle thick client when enabled by configuration.

    Purpose:
        Switches python-oracledb to thick mode to handle password verifier formats
        unsupported in thin mode (e.g., DPY-3015).
    Inputs:
        None; uses module-level configuration flags and environment variables.
    Outputs:
        None directly; raises exceptions if client initialization fails.
    """
    global _ORACLE_CLIENT_INITIALIZED

    # Return early when thick mode is disabled or initialization already executed.
    if _ORACLE_CLIENT_INITIALIZED or not use_thick_mode:
        return

    try:
        # Initialize Instant Client with optional explicit lib_dir path when provided.
        client_dir = oracle_client_lib_dir if len(oracle_client_lib_dir) > 0 else None
        oracledb.init_oracle_client(lib_dir=client_dir)
        _ORACLE_CLIENT_INITIALIZED = True
        add_to_log('INFO.\tOracle thick client initialized successfully.')
    except Exception as e:
        # Log detailed exception for operational visibility and re-raise to stop startup.
        add_to_log(print_exception(e))
        raise


##################################################################################
def exec_sql_cmd(sql):
    """Execute SQL against Oracle and return structured rows.

    Purpose:
        Runs a single SQL statement using configured credentials and returns results
        as a list of dictionaries (column name -> value). Handles initialization of
        the Oracle client to avoid thin-mode verifier issues.
    Inputs:
        sql (str): SQL query string prepared by upstream configuration.
    Outputs:
        tuple(bool, list|dict): success flag and result payload or error details.
    """
    result_rows, f_result = [], False
    try:
        # Ensure Oracle client is initialized before opening a connection.
        init_oracle_client_if_needed()

        # Open connection with timeout safeguards to prevent hanging threads.
        with oracledb.connect(user=user, password=pwd64, dsn=dsn, tcp_connect_timeout=5) as con:
            #print("Python lib version:", oracledb.__version__,"Database version:", con.version )
            cur = con.cursor()
            cur.execute(sql)
            #res = cur.fetchall()
            #for row in res:  print(row)
            # format result to json with data name
            for row in cur.fetchall():
                res = {}
                index = -1
                for val in row:
                    index += 1
                    #index = row.index(val)
                    val = str(val) if type(val) not in (int, str) else val
                    #res[cur.description[row.index(val)][0]] = val
                    res[cur.description[index][0]] = val
                result_rows.append(res)
        f_result = True
    except Exception as e:
        # Capture DPY-3015 specifically to guide operators toward thick mode usage.
        if 'DPY-3015' in str(e) and not use_thick_mode:
            guidance = ('ERROR.\tDPY-3015 encountered in thin mode. Set ORACLE_USE_THICK_MODE=true ' 
                        'and provide Instant Client via ORACLE_CLIENT_LIB_DIR to enable supported verifiers.')
            add_to_log(guidance)
        add_to_log(print_exception(e))
        result_rows = {'ERROR': str(e)}
    finally:
        return f_result, result_rows


def get_sql_data(cmd):
    add_to_log(f'INFO.\tStart SQL request: {cmd}')
    begin_time = datetime.now()
    sql_list = get_configs(os.path.join('config', 'sql.lib.json'))
    cache_timeout_s = sql_list.get(cmd, {}).get('cache_timeout_s', default_cache_timeout_s)
    # check results in cache
    f_data = get_sql_cache(cmd, cache_timeout_s)
    if len(f_data) > 0:
        f_result = True
    else:
        # get from DB if cache is empty
        eSQL = sql_list.get(cmd, {}).get('sql', 'na')
        f_result, f_data = exec_sql_cmd(eSQL) if eSQL != 'na' else (False, {'ERROR': 'Unknown SQL.'})
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
        data, duration = get_sql_data(get_sql_data(argv[1]))
        add_to_log(f'INFO.\tRequest return data length: {len(data)}.')
        exit(0) if len(data) > 0 else exit(1)
    else:
        add_to_log('WARNING.\tArguments must be 1. Usage: \"script_name.py sql_cmf_name\"')
