def format_currency(value):
    """
    格式化金額
    
    Args:
        value: 數值或字串
        
    Returns:
        str: 格式化後的金額字串 (例: $10,000)
    """
    if value is None:
        return "$0"
    try:
        if isinstance(value, str):
            value = float(value)
        return f"${int(value):,}"
    except (ValueError, TypeError):
        return str(value)
