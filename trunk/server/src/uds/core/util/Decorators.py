'''
Created on Feb 6, 2012

@author: dkmaster
'''

from time import sleep
from functools import wraps

# Have to test these decorators before using them
def retryOnException(retries=3, delay = 0):
    '''
    Decorator to retry 
    '''
    def decorator(func):
        @wraps(func)
        def _wrapped_func(*args, **kwargs):
            while retries > 0:
                retries -= 1
                try: 
                    return func(*args, **kwargs)
                except Exception:
                    if retries == 0:
                        raise
                    if delay > 0:
                        sleep(delay)
        return _wrapped_func
    return decorator
