import json
import re

def safe_json_loads(text):
    if hasattr(text, 'text'):
        text = text.text
    if isinstance(text, (dict, list)):
        return text
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r',\s*([\}\]])', r'\1', text)
        cleaned = cleaned.strip()
        
        if cleaned.startswith('{') and not cleaned.endswith('}'):
            if cleaned.count('"') % 2 != 0:
                cleaned += '"'
            # try to close up to 3 levels if it's deeply nested, but simple '}' is what the user had
            cleaned += '}'
            # se faltar fechar mais de uma, adicionaremos
            while cleaned.count('{') > cleaned.count('}'):
                cleaned += '}'
        elif cleaned.startswith('[') and not cleaned.endswith(']'):
            if cleaned.count('"') % 2 != 0:
                cleaned += '"'
            while cleaned.count('[') > cleaned.count(']'):
                cleaned += ']'
            
        try:
            return json.loads(cleaned)
        except Exception as e:
            raise Exception(f"Malformed JSON from bank API could not be parsed: {text[:500]}")
