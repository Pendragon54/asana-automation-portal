# parsers.py (v2.0)
import re

def parse_cal_cert_title(title: str) -> dict:
    """
    Parses an Asana task title using Regular Expressions to reliably
    extract certificate data.
    
    Args:
        title: The Asana task title string.
        
    Returns:
        A dictionary containing the parsed data.
    """
    
    # Define regex patterns for each piece of data
    patterns = {
        'model_number': r":\s*([^\s]+)",  # Text after the first colon
        'serial_number': r"SN:\s*(\S+)",  # Text after "SN: "
        'range': r"(\d*\.?\d+)\s*Torr",  # Number before "Torr"
        'fitting': r"(\S*VCR\S*)",       # Word containing "VCR"
        'connector': r"(\S*pin\S*)",     # Word containing "pin"
        'orientation': r"(vertical|horizontal)" # The word "vertical" or "horizontal"
    }
    
    parsed_data = {}
    
    # Run each pattern and store the result
    for key, pattern in patterns.items():
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            parsed_data[key] = match.group(1).strip()
        else:
            parsed_data[key] = "NOT FOUND"
            
    # Handle the default orientation
    if parsed_data['orientation'] == "NOT FOUND":
        parsed_data['orientation'] = "vertical"
        
    # Combine range with "Torr"
    if parsed_data['range'] != "NOT FOUND":
        parsed_data['range'] = f"{parsed_data['range']} Torr"
        
    return parsed_data