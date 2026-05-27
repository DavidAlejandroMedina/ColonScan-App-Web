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

@register.filter
def date_or_default(value, format_string="d/m/Y", default_text="No evaluado"):
    """
    Format a date field, or return a default text if None/empty.
    Usage: {{ patient.last_evaluation_date|date_or_default:"d/m/Y" }}
           {{ patient.last_evaluation_date|date_or_default:"d/m/Y":"Sin información" }}
    """
    if not value:
        return default_text
    
    try:
        from django.template.defaultfilters import date as date_filter
        formatted = date_filter(value, format_string)
        # If date filter returns empty string, return default
        return formatted if formatted else default_text
    except Exception:
        return default_text


@register.filter
def format_processing_time(value):
    """Format seconds as Xm Ys when >= 60, otherwise Xs."""
    if value is None or value == "":
        return ""

    try:
        total_seconds = int(round(float(value)))
    except (TypeError, ValueError):
        return ""

    if total_seconds < 60:
        return f"{total_seconds}s"

    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds}s"
