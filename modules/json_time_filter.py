"""
Time range filter module for Grafana $__from / $__to integration.
Filters JSON rows by datetime fields using from/to query parameters.
"""
from urllib.parse import parse_qs
from datetime import datetime


DATE_FORMATS = [
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d',
]


def _parse_datetime(value):
    if not isinstance(value, str) or not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_time_param(value):
    if not value:
        return None
    value = value.strip()
    if value.isdigit() and len(value) > 10:
        return datetime.fromtimestamp(int(value) / 1000)
    return _parse_datetime(value)


def _detect_time_field(row):
    if not isinstance(row, dict):
        return None
    for key, val in row.items():
        if _parse_datetime(val) is not None:
            return key
    return None


def _get_field_value(row, field):
    if not isinstance(row, dict):
        return None
    val = row.get(field)
    if val is not None:
        return val
    field_lower = field.lower()
    for k, v in row.items():
        if k.lower() == field_lower:
            return v
    return None


def apply_time_filter(data, query_string):
    """
    Filter data rows by time range.
    Params: from, to (epoch ms or ISO string), time_field (optional field name override).
    Returns data unchanged if from/to not provided or data is not a list.
    """
    if not isinstance(data, list) or not data:
        return data

    params = parse_qs(query_string, keep_blank_values=False)

    from_raw = params.get('from', [None])[0]
    to_raw = params.get('to', [None])[0]

    if not from_raw and not to_raw:
        return data

    time_from = _parse_time_param(from_raw) if from_raw else None
    time_to = _parse_time_param(to_raw) if to_raw else None

    if not time_from and not time_to:
        return data

    time_field_param = params.get('time_field', [None])[0]

    if time_field_param:
        time_field = time_field_param
    else:
        time_field = _detect_time_field(data[0])
        if not time_field:
            return data

    result = []
    for row in data:
        val = _get_field_value(row, time_field)
        row_dt = _parse_datetime(val)
        if row_dt is None:
            continue
        if time_from and row_dt < time_from:
            continue
        if time_to and row_dt > time_to:
            continue
        result.append(row)

    return result
