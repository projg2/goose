# (c) 2020 Michał Górny
# 2-clause BSD license

"""
WSGI config for anser project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anser.settings')

application = get_wsgi_application()
