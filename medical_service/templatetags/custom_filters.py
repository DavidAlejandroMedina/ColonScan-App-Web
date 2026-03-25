from django import template
from datetime import datetime

register = template.Library()

@register.filter
def parse_iso_date(value, format_string="d/m/Y"):
    """
    Parse ISO format datetime string and format it.
    Usage: {{ value|parse_iso_date:"d/m/Y" }}
    """
    if not value:
        return ""
    
    try:
        # Parse ISO format string
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
        else:
            dt = value
        
        # Format the datetime based on format_string
        format_map = {
            "d/m/Y": "%d/%m/%Y",
            "H:i": "%H:%M",
            "Y-m-d": "%Y-%m-%d",
            "Y-m-d H:i": "%Y-%m-%d %H:%M",
        }
        
        format_spec = format_map.get(format_string, format_string)
        return dt.strftime(format_spec)
    except Exception as e:
        return f"Error parsing date: {str(e)}"

@register.filter
def iso_time(value):
    """
    Extract time from ISO format datetime string.
    Usage: {{ value|iso_time }}
    """
    if not value:
        return ""
    
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            return dt.strftime("%H:%M")
        return value
    except Exception:
        return ""
