"""
JSON post-processing filter module
Supports: filter, fields, limit, sort query parameters
"""
from urllib.parse import parse_qs


OPERATORS = {
    'eq': lambda val, target: str(val).lower() == target.lower(),
    'neq': lambda val, target: str(val).lower() != target.lower(),
    'contains': lambda val, target: target.lower() in str(val).lower(),
    'gt': lambda val, target: _to_number(val) > _to_number(target),
    'lt': lambda val, target: _to_number(val) < _to_number(target),
    'gte': lambda val, target: _to_number(val) >= _to_number(target),
    'lte': lambda val, target: _to_number(val) <= _to_number(target),
    'in': lambda val, target: str(val).lower() in [t.strip().lower() for t in target.split(',')],
}


def _to_number(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def _get_row_value(row, field):
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


def _get_actual_key(row, field):
    if not isinstance(row, dict):
        return field
    if field in row:
        return field
    field_lower = field.lower()
    for k in row:
        if k.lower() == field_lower:
            return k
    return field


def _parse_filter(filter_str):
    parts = filter_str.split(':', 2)
    if len(parts) != 3:
        return None
    field, op, value = parts
    if op not in OPERATORS:
        return None
    return field, op, value


def _apply_single_filter(data, field, op, value):
    result = []
    op_func = OPERATORS[op]
    for row in data:
        if field == '*':
            if not isinstance(row, dict):
                continue
            if any(op_func(v, value) for v in row.values() if v is not None):
                result.append(row)
        else:
            row_val = _get_row_value(row, field)
            if row_val is None and op == 'neq':
                result.append(row)
            elif row_val is not None and op_func(row_val, value):
                result.append(row)
    return result


def _apply_fields(data, fields_str):
    fields = [f.strip() for f in fields_str.split(',') if f.strip()]
    if not fields:
        return data
    result = []
    for row in data:
        if not isinstance(row, dict):
            continue
        projected = {}
        for f in fields:
            actual_key = _get_actual_key(row, f)
            projected[actual_key] = row.get(actual_key)
        result.append(projected)
    return result


def _apply_sort(data, sort_str):
    parts = sort_str.split(':')
    field = parts[0]
    reverse = len(parts) > 1 and parts[1].lower() == 'desc'

    def sort_key(row):
        val = _get_row_value(row, field)
        if val is None:
            return (1, '')
        try:
            return (0, float(val))
        except (ValueError, TypeError):
            return (0, str(val).lower())

    return sorted(data, key=sort_key, reverse=reverse)


def apply_filters(data, query_string):
    """
    Apply filters to data based on query string parameters.
    Returns filtered data in the same format as input (list or dict).
    """
    if not isinstance(data, list):
        return data

    params = parse_qs(query_string, keep_blank_values=False)
    result = data

    filters = params.get('filter', [])
    for f in filters:
        parsed = _parse_filter(f)
        if parsed:
            field, op, value = parsed
            result = _apply_single_filter(result, field, op, value)

    if 'sort' in params:
        result = _apply_sort(result, params['sort'][0])

    if 'fields' in params:
        result = _apply_fields(result, params['fields'][0])

    if 'limit' in params:
        try:
            limit = int(params['limit'][0])
            if limit > 0:
                result = result[:limit]
        except ValueError:
            pass

    return result
