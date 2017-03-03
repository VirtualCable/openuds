import six

if six.PY2:
    import sys

    # noinspection PyCompatibility
    reload(sys)

    # noinspection PyUnresolvedReferences
    sys.setdefaultencoding('utf-8')  # @UndefinedVariable
