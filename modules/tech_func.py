import os, time, re, inspect, json, yaml
from colorist import Color
from datetime import datetime, timedelta


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def log_add(err_str, print_errors=True):
    try:
        ensure_dir('logs')
        cdate = str(datetime.now())
        with open(os.path.join('logs', 'server.http.log'), "a") as logfile:
            logfile.write('\n' + cdate + '\t' + str(err_str))
            if print_errors:
                print(cdate + '\t' + str(err_str))
    except Exception as e:
        print("# Error. Func log_add: " + str(e))
    return 0


def get_file_content(filename, basedir=os.path.join('sql')):
    try:
        with open(os.path.join(basedir, filename), 'r', encoding="utf8") as conf_file:
            lines = conf_file.readlines()
            return '\n'.join([line.strip() for line in lines])
    except Exception as e:
        add_to_log(f'ERROR.\tError when read SQL file "{filename}". Error: {e}')
        return None


def get_configs(filename: str, fast_mode: bool = False):
    try:
        with open(filename, 'r') as conf_file:
            if re.search('.*json', filename):
                result = json.load(conf_file)
            elif re.search('.*yml', filename):
                result = yaml.safe_load(conf_file)
            result = get_conf_from_osenv_or_file(result, os_search_val='os_env') if not fast_mode else result
        return result
    except Exception as e:
        add_to_log(f'ERROR.\tError when get config_global. From: "{filename}". Error: {e}.')
        return {}


def get_conf_from_osenv_or_file(mydic: dict, os_search_val='os_env'):
    if type(mydic) != dict:
        return mydic

    result = mydic
    for key, val in mydic.items():
        if type(val) == dict:
            result[key] = get_conf_from_osenv_or_file(val)
        elif val == os_search_val:
            result[key] = os.getenv(key)
        elif (type(val) is str) and (re.search(r'.*\.sql$', val)):
            result[key] = get_file_content(val)
    return result


def add_to_log(err_str: str, class_name: str = '', filename: str = '', print2console: bool = True):
    config_loglevel = 'INFO'
    func_data = inspect.stack()[1]
    parent_module = re.findall("[A-z-_0-9]*", os.path.basename(func_data.filename))[0]
    parent_func = func_data.function

    if filename == '':
        filename = parent_module + '.log'

    class_name = class_name + '->' if len(class_name) > 2 else ''
    err_str = str(datetime.now()) + '\tFunction: ' + class_name + parent_func + '\t' + err_str.replace('\r', '').replace('\n', '\t')
    try:
        ensure_dir('logs')
        with open(os.path.join("logs", filename), "a") as logfile:
            logfile.write(err_str + '\n')
            result = True
    except Exception as e:
        print(datetime.now(), 'Error in add_to_log:', e)
        print(err_str)
        result = False
    if print2console:
        log_levels = "DEBUG|INFO|WARNING|ERROR|CRITICAL|FATAL|SUCCESS"
        current_levels = "\t(" + log_levels[log_levels.index(config_loglevel):] + ").?\t"
        if re.search(current_levels, err_str):
            err_str = err_str.replace('\n', ' ')

            err_str = err_str \
                .replace("INFO", f"{Color.BLUE}INFO{Color.OFF}") \
                .replace("WARNING", f"{Color.YELLOW}WARNING{Color.OFF}") \
                .replace("ERROR", f"{Color.RED}ERROR{Color.OFF}") \
                .replace("FATAL", f"{Color.RED}FATAL{Color.OFF}") \
                .replace("CRITICAL", f"{Color.RED}CRITICAL{Color.OFF}") \
                .replace("SUCCESS", f"{Color.GREEN}SUCCESS{Color.OFF}")

            print(err_str)
    return result


def print_exception(exc: Exception):
    return 'ERROR' + '.\tLine: ' + str(exc.__traceback__.tb_lineno) + '.\t' + str(exc.__class__) + '|' + str(exc)


def set_config(conf, filename):
    try:
        ensure_dir(os.path.dirname(filename))
        with open(filename, 'w', encoding='utf-8') as conf_file:
            if re.search('.*json', filename):
                return json.dump(conf, conf_file)
            elif re.search('.*yml', filename):
                return yaml.dump(conf, conf_file)
    except Exception as e:
        add_to_log(f'ERROR.\tError when get config_global. From: "{filename}". Error: {e}.')
        exit(126)

if __name__ == "__main__":
    print('Error. Cant usage as main.')
    exit(1)
