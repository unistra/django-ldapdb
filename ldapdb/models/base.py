# -*- coding: utf-8 -*-
# 
# django-ldapdb
# Copyright (c) 2009-2011, Bolloré telecom
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

from django.conf import settings
from django.core import exceptions
from django.db import connections, router
from django.db.models import signals
import django.db.models
import ldap
import logging

class QuerySet(django.db.models.query.QuerySet):

    def using(self, alias):
        """
        Selects which database this QuerySet should execute it's query against,
        but change model base_dn to avoid errors.
        """
        clone = self._clone()
        clone._db = alias
        return clone

class ModelManager(django.db.models.manager.Manager):

    def get_query_set(self):
        # force using to choose right server
        return QuerySet(self.model, using=self._db).using(self._db)

    def using(self,alias):
        return self.get_query_set().using(alias)

class Model(django.db.models.base.Model):
    """
    Base class for all LDAP models.
    """
    dn = django.db.models.fields.CharField(max_length=200)
    
    base_dn = None
    search_scope = ldap.SCOPE_SUBTREE
    object_classes = ['top']

    objects = ModelManager()

    @classmethod
    def get_base_dn(self,alias):
        try:
            conn_dict = settings.DATABASES[alias]
        except KeyError:
            raise exceptions.ImproperlyConfigured,u"Connection settings for '%s' not found. Please, setup a connection in DATABASES configuration at settings.py" % alias
        else:
            try:
                return conn_dict['BASE_DN']
            except KeyError:
                raise exceptions.ImproperlyConfigured,u"Connections settings for '%(conn)s' found, but BASE_DN for '%(conn)s' not found in settings. Please configure a BASE_DN for connection '%(conn)s'." % {'conn': alias}

    @property
    def base_dn(self):
        # backwards compatibility
        try:
            return self.__class__.get_base_dn(self._state.db)
        except Exception:
            raise ValueError,u"Unknow connection. Need a instance to know the connection."

    @property
    def using(self):
        try:
            return self._state.db
        except Exception:
            raise ValueError,u"Unknow connection. Need a instance to know the connection."

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        self.saved_pk = self.pk

    def build_rdn(self):
        """
        Build the Relative Distinguished Name for this entry.
        """
        bits = []
        for field in self._meta.fields:
            if field.db_column and field.primary_key:
                bits.append("%s=%s" % (field.db_column, getattr(self, field.name)))
        if not len(bits):
            raise Exception("Could not build Distinguished Name")
        return '+'.join(bits)

    def build_dn(self):
        """
        Build the Distinguished Name for this entry.
        """
        return "%s,%s" % (self.build_rdn(), self.base_dn)
        raise Exception("Could not build Distinguished Name")

    def delete(self, using=None):
        """
        Delete this entry.
        """
        using = using or router.db_for_write(self.__class__, instance=self)
        connection = connections[using]
        logging.debug("Deleting LDAP entry %s" % self.dn)
        connection.delete_s(self.dn)
        signals.post_delete.send(sender=self.__class__, instance=self)

    def save(self, using=None, **kwargs):
        """
        Saves the current instance.
        """
        using = using or router.db_for_write(self.__class__, instance=self)
        connection = connections[using]
        if not self.dn:
            # create a new entry
            record_exists = False 
            entry = [('objectClass', self.object_classes)]
            new_dn = self.build_dn()

            for field in self._meta.fields:
                if not field.db_column:
                    continue
                try:
                    value = getattr(self, field.name)
                except field.rel.to.DoesNotExist:
                    value = None
                if value:
                    entry.append((field.db_column, field.get_db_prep_save(value, connection=connection)))

            logging.debug("Creating new LDAP entry %s" % new_dn)
            connection.add_s(new_dn, entry)

            # update object
            self.dn = new_dn

        else:
            # update an existing entry
            record_exists = True
            modlist = []
            # force use of alias in 'self.using' if any alias are sent in args.
            try:
                orig = self.__class__.objects.using(using or self._state.db ).get(pk=self.saved_pk)
            except Exception:
                raise ValueError,u"Unknow connection. Need a instance to know the connection."
            for field in self._meta.fields:
                if not field.db_column:
                    continue
                try:
                    old_value = getattr(orig, field.name, None)
                except field.rel.to.DoesNotExist:
                    old_value = None
                try:
                    new_value = getattr(self, field.name, None)
                except field.rel.to.DoesNotExist:
                    new_value = None
                if old_value != new_value:
                    if new_value or isinstance(new_value, bool):
                        modlist.append((ldap.MOD_REPLACE, field.db_column, field.get_db_prep_save(new_value, connection=connection)))
                    elif old_value or isinstance(old_value, bool):
                        modlist.append((ldap.MOD_DELETE, field.db_column, None))

            if len(modlist):
                # handle renaming
                new_dn = self.build_dn()
                if new_dn != self.dn:
                    logging.debug("Renaming LDAP entry %s to %s" % (self.dn, new_dn))
                    # change the branch of account in the tree
                    if self.base_dn not in self.dn:
                        connection.rename_s(self.dn,
                                            self.build_rdn(),
                                            newsuperior=self.base_dn)
                    else:
                        connection.rename_s(self.dn, self.build_rdn())
                    connection.rename_s(self.dn, self.build_rdn())
                    self.dn = new_dn
            
                logging.debug("Modifying existing LDAP entry %s" % self.dn)
                connection.modify_s(self.dn, modlist)
            else:
                logging.debug("No changes to be saved to LDAP entry %s" % self.dn)

        # done
        self.saved_pk = self.pk
        signals.post_save.send(sender=self.__class__, instance=self, created=(not record_exists))

    #@classmethod
    #def scoped(base_class, base_dn):
    #    """
    #    Returns a copy of the current class with a different base_dn.
    #    """
    #    import new
    #    import re
    #    suffix = re.sub('[=,]', '_', base_dn)
    #    name = "%s_%s" % (base_class.__name__, str(suffix))
    #    new_class = new.classobj(name, (base_class,), {'base_dn': base_dn, '__module__': base_class.__module__})
    #    return new_class
    #
    # This commented version are from previous versions but works, don't know
    # if new version can work

    @classmethod
    def scoped(base_class, base_dn):
        """
        Returns a copy of the current class with a different base_dn.
        """
        class Meta:
            proxy = True
        import re
        suffix = re.sub('[=,]', '_', base_dn)
        name = "%s_%s" % (base_class.__name__, str(suffix))
        new_class = type(name, (base_class,), {'base_dn': base_dn, '__module__': base_class.__module__, 'Meta': Meta})
        return new_class

    class Meta:
        abstract = True
