import re

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title)