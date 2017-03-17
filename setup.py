#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name = "django-ldapdb",
    version = "1.0.9",
    #license = ldapdb.__license__,
    url = "http://opensource.bolloretelecom.eu/projects/django-ldapdb/",
    author = "Jeremy Laine",
    author_email = "jeremy.laine@bolloretelecom.eu",
    packages = find_packages(),
    zip_safe = False,
    install_requires=[
        'six',
        'python-ldap;python_version<"3.0"',
        'pyldap;python_version>="3.0"',
    ]
)
