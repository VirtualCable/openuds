import string

# constants
# String chars to use in random strings
STRING_CHARS = string.ascii_letters + string.digits + '_'
# Invalid string chars
STRING_CHARS_INVALID = '!@#$%^&*()_+=-[]{}|;\':",./<>? '
# String chars with invalid chars to use in random strings
STRING_CHARS_WITH_INVALID = STRING_CHARS + STRING_CHARS_INVALID

