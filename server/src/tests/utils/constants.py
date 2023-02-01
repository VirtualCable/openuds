import string

# constants
# String chars to use in random strings
STRING_CHARS = string.ascii_letters + string.digits + '_'
UTF_CHARS = (
    'abcdefghijklπερισσότεροήλιγότερομεγάλοκείμενογιαχαρακτήρεςmnopqrstuvwxyz或多或少的字符长文本ABCD'
    'EFGHIJKLنصطويلأكثرأوأقلللأحرفMNOPQRSTUVWXYZ0123456789болееилименеедлинныйтекстдлясимволовàáéíóúñçÀÁÉÍÓÚÑÇ'
)
# Invalid string chars
STRING_CHARS_INVALID = '!@#$%^&*()_+=-[]{}|;\':",./<>? '
# String chars with invalid chars to use in random strings
STRING_CHARS_WITH_INVALID = STRING_CHARS + STRING_CHARS_INVALID

