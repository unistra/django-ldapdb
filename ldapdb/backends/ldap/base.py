# -*- coding: utf-8 -*-
# 
# django-ldapdb
# Copyright (c) 2009-2010, Bolloré telecom
# All rights reserved.
# 
# See AUTHORS file for a full list of contributors.
# 
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
# 
#     1. Redistributions of source code must retain the above copyright notice, 
#        this list of conditions and the following disclaimer.
#     
#     2. Redistributions in binary form must reproduce the above copyright 
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
# 
#     3. Neither the name of Bolloré telecom nor the names of its contributors
#        may be used to endorse or promote products derived from this software
#        without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import django
import ldap
from ldap.controls import SimplePagedResultsControl
from django.conf import settings
from django.db.backends import BaseDatabaseFeatures, BaseDatabaseOperations, BaseDatabaseWrapper
from django.db.backends.creation import BaseDatabaseCreation

class DatabaseCreation(BaseDatabaseCreation):
    def create_test_db(self, verbosity=1, autoclobber=False, serialize=True):
        """
        Creates a test database, prompting the user for confirmation if the
        database already exists. Returns the name of the test database created.
        """
        pass

    def destroy_test_db(self, old_database_name, verbosity=1):
        """
        Destroy a test database, prompting the user for confirmation if the
        database already exists. Returns the name of the test database created.
        """
        pass

class DatabaseCursor(object):
    def __init__(self, ldap_connection):
        self.connection = ldap_connection

class DatabaseFeatures(BaseDatabaseFeatures):
    def __init__(self, connection):
        self.connection = connection
        self.supports_transactions = False

class DatabaseOperations(BaseDatabaseOperations):
    compiler_module = "ldapdb.backends.ldap.compiler"

    def quote_name(self, name):
        return name

class DatabaseWrapper(BaseDatabaseWrapper):
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)

        self.charset = "utf-8"
        self.creation = DatabaseCreation(self)
        self.features = DatabaseFeatures(self)
        if django.VERSION > (1, 4):
            self.ops = DatabaseOperations(self)
        else:
            self.ops = DatabaseOperations()
        self.settings_dict['SUPPORTS_TRANSACTIONS'] = False

    def close(self):
        if hasattr(self, 'validate_thread_sharing'):
            # django >= 1.4
            self.validate_thread_sharing()
        if self.connection is not None:
            self.connection.unbind_s()
            self.connection = None

    def _commit(self):
        pass

    def _cursor(self):
        if self.connection is None:
            #self.connection = ldap.initialize(self.settings_dict['NAME'])
            self.connection = ldap.ldapobject.ReconnectLDAPObject(
                    uri=self.settings_dict['NAME'],
                    trace_level=0,
                    )

            self.connection.simple_bind_s(
                self.settings_dict['USER'],
                self.settings_dict['PASSWORD'])

            # Allow custom options to ldap. Active directory should set
            # ldap.OPT_REFERRALS as 0, or it not work.
            ldap_options = getattr(settings,'LDAPDB_LDAP_OPTIONS',{})
            for opt_name,opt_value in ldap_options.items():
                    self.connection.set_option(opt_name,opt_value)

            #self.connection.set_option(ldap.OPT_TIMEOUT,1)
            #self.connection.set_option(ldap.OPT_TIMELIMIT,1)

        return DatabaseCursor(self.connection)

    def _rollback(self):
        pass

    def _paged_search(self, connection, base, scope, filterstr, attrlist):
        page_size = self.settings_dict.get('PAGE_SIZE', 1000)
        results = []
        pg_ctrl = SimplePagedResultsControl(True, page_size, "")
        scope = ldap.SCOPE_SUBTREE
        pages = 0

        while True:
            pages += 1
            msgid = connection.search_ext(
                base,
                scope=scope,
                filterstr=filterstr,
                attrlist=attrlist,
                serverctrls=[pg_ctrl]
            )
            rtype, rdata, rmsgid, serverctrls = connection.result3(msgid)
            results.extend(rdata)
            cookie = serverctrls[0].cookie
            if cookie:
                pg_ctrl.cookie = cookie
                search = connection.search_ext(
                    base,
                    scope=scope,
                    filterstr=filterstr,
                    attrlist=attrlist,
                    serverctrls=[pg_ctrl]
                )
            else:
                break

        return results

    def bind_s(self, dn, password):
        cursor = self._cursor()
        return cursor.connection.bind_s(dn, password, ldap.AUTH_SIMPLE)

    def add_s(self, dn, modlist):
        cursor = self._cursor()
        return cursor.connection.add_s(dn, modlist)

    def delete_s(self, dn):
        cursor = self._cursor()
        return cursor.connection.delete_s(dn)

    def modify_s(self, dn, modlist):
        cursor = self._cursor()
        return cursor.connection.modify_s(dn, modlist)

    def rename_s(self, dn, newrdn, newsuperior=None, delold=1):
        cursor = self._cursor()
        return cursor.connection.rename_s(dn,
                                          newrdn,
                                          newsuperior=newsuperior,
                                          delold=delold)

    def search_s(self, base, scope, filterstr='(objectClass=*)',attrlist=None):
        cursor = self._cursor()
        pagination = self.settings_dict.get('SUPPORTS_PAGINATION', False)
        results = []
        
        if pagination:
            results = self._paged_search(cursor.connection, base, scope, filterstr, attrlist)
        else:
            results = cursor.connection.search_s(base, scope, filterstr, attrlist)

        output = []
        for dn, attrs in results:
            # In tests, Active Directory always return last line as 
            # (None, ['ldap://DomainDnsZones.mydomain.corp/DC=DomainDnsZones,DC=mydomain,DC=corp'])]
            # so we check for DN and avoid errors on results.
            if dn:
                output.append((dn, attrs))
        return output

