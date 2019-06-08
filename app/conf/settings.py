import os

is_docker = os.environ.get('IS_IN_CONTAINER', False)

if is_docker:
    from .docker import *
else:
    from .development import *
