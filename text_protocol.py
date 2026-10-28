"""Explicit test-text wire format: decode codepoints, never guess escape intent."""
TEXT_KEY = '__am_text__'

TEXT_FORMAT = (
    'For EVERY string value in test args and expected, use the explicit object '
    '{"__am_text__":[integer Unicode codepoints]} instead of a JSON string. '
    'Empty text is {"__am_text__":[]}; one space is {"__am_text__":[32]}; '
    'a newline character is {"__am_text__":[10]}; two literal quote characters are '
    '{"__am_text__":[34,34]}; the two literal characters backslash+n are '
    '{"__am_text__":[92,110]}. Do not wrap these objects or their contents in quotes. '
    'These objects become ordinary strings before the function is called. '
    'Use this envelope ONLY for text: integers, booleans, numbers, and integer arrays '
    'must remain native JSON values, never codepoint objects. '
    'Metadata, hints, and source code fields remain normal JSON strings. '
)


def text_schema(language=None):
    return {'type':'object', 'additionalProperties':False, 'required':[TEXT_KEY],
            'properties':{TEXT_KEY:{'type':'array','maxItems':1000,
                'items':{'type':'integer','minimum':1 if language=='c' else 0,
                         'maximum':127 if language in ('c','cpp','java') else 0x10ffff}}}}


def decode_text(value, depth=0):
    if depth>8:
        raise ValueError('Test values are nested too deeply.')
    if isinstance(value,dict):
        if TEXT_KEY in value:
            points=value[TEXT_KEY]
            if (set(value)!={TEXT_KEY} or not isinstance(points,list) or len(points)>1000 or
                    any(type(point) is not int or not 0<=point<=0x10ffff or 0xd800<=point<=0xdfff
                        for point in points)):
                raise ValueError('Text codepoints must be at most 1000 valid Unicode scalar integers.')
            return ''.join(chr(point) for point in points)
        return {key:decode_text(item,depth+1) for key,item in value.items()}
    if isinstance(value,list):
        return [decode_text(item,depth+1) for item in value]
    # Legacy raw strings are literal and unchanged: never strip quotes/unescape.
    return value
