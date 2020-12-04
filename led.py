internal_value = 0

def value(v=None):
    global internal_value
    if not v is None:
        internal_value = v
    return internal_value
