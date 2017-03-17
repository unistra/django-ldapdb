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

from collections import Counter
import re

from django.db import connections, router
from django.db.models import Q
from django.test import TestCase
import mock
from mockldap import MockLdap
import six

from ldapdb.backends.ldap.compiler import query_as_ldap
from examples.models import LdapUser, LdapGroup


def mock_rename_s(obj, dn, newrdn, newsuperior=None, delold=1):
    cursor = obj._cursor()
    return cursor.connection.rename_s(dn,
                                      newrdn,
                                      newsuperior=newsuperior)


class BaseTestCase(TestCase):

    nodomain = ('dc=nodomain', {'dc': 'nodomain'})
    groups = ('ou=groups,dc=nodomain', {'ou': 'groups'})
    people = ('ou=people,dc=nodomain', {'ou': 'people'})
    contacts = ('ou=contacts,ou=groups,dc=nodomain', {'ou': 'contacts'})
    directory = dict([nodomain, groups, people, contacts])

    @classmethod
    def setUpClass(cls):
        cls.mockldap = MockLdap(cls.directory)

    @classmethod
    def tearDownClass(cls):
        del cls.mockldap

    def setUp(self):
        self.mockldap.start(path='ldap.ldapobject.ReconnectLDAPObject')

    def tearDown(self):
        self.mockldap.stop(path='ldap.ldapobject.ReconnectLDAPObject')

    # def _add_base_dn(self, model):
    #     base_dn = model.base_dn
    #     entry = base_dn.split(',')[0].split('=')
    #     self.directory[base_dn] = dict([entry])

class GroupTestCase(BaseTestCase):

    def setUp(self):
        super(GroupTestCase, self).setUp()

        LdapGroup.objects.create(
            name='foogroup', gid=1000, usernames=['foouser', 'baruser'])
        LdapGroup.objects.create(
            name='bargroup', gid=1001, usernames=['zoouser', 'baruser'])
        LdapGroup.objects.create(
            name='wizgroup', gid=1002, usernames=['wizuser', 'baruser'])

    def assertQueryAsLdapEqual(self, ldap_filter, value):
        pattern = '(\(\w*=\w*\))'
        self.assertTrue(
            all([
                len(ldap_filter) == len(value),
                Counter(ldap_filter) == Counter(value),
                Counter(re.findall(pattern, ldap_filter)) ==
                Counter(re.findall(pattern, ldap_filter))
            ]),
            "'%s' does not match query '%s'" % (ldap_filter, value)
        )

    def test_count(self):
        # empty query
        qs = LdapGroup.objects.none()
        self.assertEquals(qs.count(), 0)

        qs = LdapGroup.objects.none()
        self.assertEquals(len(qs), 0)

        # all query
        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 3)

        qs = LdapGroup.objects.all()
        self.assertEquals(len(qs), 3)

    def test_ldap_filter(self):
        # single filter
        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(cn=foogroup))')

        qs = LdapGroup.objects.filter(Q(name='foogroup'))
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(cn=foogroup))')

        qs = LdapGroup.objects.filter(gid=1000, name='foogroup')
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(&(gidNumber=1000)(cn=foogroup)))')

        qs = LdapGroup.objects.filter(Q(gid=1000) & Q(name='foogroup'))
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(&(gidNumber=1000)(cn=foogroup)))')

        # OR filter
        qs = LdapGroup.objects.filter(Q(gid=1000) | Q(name='foogroup'))
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(|(gidNumber=1000)(cn=foogroup)))')

        # single exclusion
        qs = LdapGroup.objects.exclude(name='foogroup')
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(!(cn=foogroup)))')
        
        qs = LdapGroup.objects.filter(~Q(name='foogroup'))
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(!(cn=foogroup)))')

        # multiple exclusion
        qs = LdapGroup.objects.exclude(name='foogroup', gid=1000)
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(!(&(gidNumber=1000)(cn=foogroup))))')

        qs = LdapGroup.objects.filter(name='foogroup').exclude(gid=1000)
        self.assertQueryAsLdapEqual(query_as_ldap(qs.query), '(&(objectClass=posixGroup)(&(cn=foogroup)(!(gidNumber=1000))))')

    def test_filter(self):
        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEquals(qs.count(), 1)

        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEquals(len(qs), 1)

        g = qs[0]
        self.assertEquals(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEquals(g.name, 'foogroup')
        self.assertEquals(g.gid, 1000)
        self.assertEquals(g.usernames, ['foouser', 'baruser'])

        # try to filter non-existent entries
        qs = LdapGroup.objects.filter(name='does_not_exist')
        self.assertEquals(qs.count(), 0)

        qs = LdapGroup.objects.filter(name='does_not_exist')
        self.assertEquals(len(qs), 0)

    def test_get(self):
        g = LdapGroup.objects.get(name='foogroup')
        self.assertEquals(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEquals(g.name, 'foogroup')
        self.assertEquals(g.gid, 1000)
        self.assertEquals(g.usernames, ['foouser', 'baruser'])

        # try to get a non-existent entry
        self.assertRaises(LdapGroup.DoesNotExist, LdapGroup.objects.get, name='does_not_exist')

    def test_order_by(self):
        # ascending name 
        qs = LdapGroup.objects.order_by('name')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'bargroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'wizgroup')

        # descending name 
        qs = LdapGroup.objects.order_by('-name')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'wizgroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'bargroup')

        # ascending gid
        qs = LdapGroup.objects.order_by('gid')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].gid, 1000)
        self.assertEquals(qs[1].gid, 1001)
        self.assertEquals(qs[2].gid, 1002)

        # descending gid
        qs = LdapGroup.objects.order_by('-gid')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].gid, 1002)
        self.assertEquals(qs[1].gid, 1001)
        self.assertEquals(qs[2].gid, 1000)

        # ascending pk
        qs = LdapGroup.objects.order_by('pk')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'bargroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'wizgroup')

        # descending pk
        qs = LdapGroup.objects.order_by('-pk')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'wizgroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'bargroup')

    def test_bulk_delete(self):
        LdapGroup.objects.all().delete()

        qs = LdapGroup.objects.all()
        self.assertEquals(len(qs), 0)

    def test_slice(self):
        qs = LdapGroup.objects.all().order_by('gid')
        objs = list(qs)
        self.assertEquals(len(objs), 3)
        self.assertEquals(objs[0].gid, 1000)
        self.assertEquals(objs[1].gid, 1001)
        self.assertEquals(objs[2].gid, 1002)

        # limit only
        qs = LdapGroup.objects.all().order_by('gid')
        objs = qs[:2]
        self.assertEquals(objs.count(), 2)

        objs = qs[:2]
        self.assertEquals(len(objs), 2)
        self.assertEquals(objs[0].gid, 1000)
        self.assertEquals(objs[1].gid, 1001)

        # offset only
        qs = LdapGroup.objects.all().order_by('gid')
        objs = qs[1:]
        self.assertEquals(objs.count(), 2)

        objs = qs[1:]
        self.assertEquals(len(objs), 2)
        self.assertEquals(objs[0].gid, 1001)
        self.assertEquals(objs[1].gid, 1002)

        # offset and limit
        qs = LdapGroup.objects.all().order_by('gid')
        objs = qs[1:2]
        self.assertEquals(objs.count(), 1)

        objs = qs[1:2]
        self.assertEquals(len(objs), 1)
        self.assertEquals(objs[0].gid, 1001)

    @mock.patch('ldapdb.backends.ldap.base.DatabaseWrapper.rename_s',
                new=mock_rename_s)
    def test_update(self):
        g = LdapGroup.objects.get(name='foogroup')

        g.gid = 1002
        g.usernames = ['foouser2', 'baruser2']
        g.save()

        # make sure DN gets updated if we change the pk
        g.name = 'foogroup2'
        g.save()
        self.assertEquals(g.dn, 'cn=foogroup2,%s' % LdapGroup.base_dn)

    def test_values(self):
        qs = sorted(
            LdapGroup.objects.values('name'),
            key=lambda x: x['name'])
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0], {'name': 'bargroup'})
        self.assertEquals(qs[1], {'name': 'foogroup'})
        self.assertEquals(qs[2], {'name': 'wizgroup'})

    def test_values_list(self):
        qs = sorted(
            LdapGroup.objects.values_list('name'),
            key=lambda x: x[0])
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0], ('bargroup',))
        self.assertEquals(qs[1], ('foogroup',))
        self.assertEquals(qs[2], ('wizgroup',))

    def test_delete(self):
        g = LdapGroup.objects.get(name='foogroup')
        g.delete()

        qs = LdapGroup.objects.all()
        self.assertEquals(len(qs), 2)


class UserTestCase(BaseTestCase):

    def setUp(self):
        super(UserTestCase, self).setUp()

        LdapUser.objects.create(
            first_name=u"Fôo",
            last_name=u"Usér",
            full_name=u"Fôo Usér",
            group=1000,
            home_directory="/home/foouser",
            uid=2000,
            username="foouser")

    def test_get(self):
        u = LdapUser.objects.get(username='foouser')
        self.assertEquals(u.first_name, u'Fôo')
        self.assertEquals(u.last_name, u'Usér')
        self.assertEquals(u.full_name, u'Fôo Usér')

        self.assertEquals(u.group, 1000)
        self.assertEquals(u.home_directory, '/home/foouser')
        self.assertEquals(u.uid, 2000)
        self.assertEquals(u.username, 'foouser')

        self.assertRaises(LdapUser.DoesNotExist, LdapUser.objects.get, username='does_not_exist')

    @mock.patch('ldapdb.backends.ldap.base.DatabaseWrapper.rename_s',
                new=mock_rename_s)
    def test_update(self):
        u = LdapUser.objects.get(username='foouser')
        u.first_name = u'Fôo2'
        u.save()

        # make sure DN gets updated if we change the pk
        u.username = 'foouser2'
        u.save()
        self.assertEquals(u.dn, 'uid=foouser2,%s' % LdapUser.base_dn)


class ScopedTestCase(BaseTestCase):

    def test_scope(self):
        scoped_model = LdapGroup.scoped("ou=contacts,%s" % LdapGroup.base_dn)
        ScopedGroup = scoped_model

        # # create group
        g = LdapGroup.objects.create(name="foogroup", gid=1000)

        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 1)

        g2 = ScopedGroup.objects.create(name="scopedgroup", gid=5000)

        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 2)

        qs = ScopedGroup.objects.all()
        self.assertEquals(qs.count(), 1)

        g2 = ScopedGroup.objects.get(name="scopedgroup")
        self.assertEquals(g2.name, u'scopedgroup')
        self.assertEquals(g2.gid, 5000)


class AdminTestCase(BaseTestCase):
    fixtures = ['test_users.json']

    def setUp(self):
        super(AdminTestCase, self).setUp()

        LdapGroup.objects.create(
            name="foogroup", gid=1000, usernames=['foouser', 'baruser'])

        LdapGroup.objects.create(
            name="bargroup", gid=1001, usernames=['zoouser', 'baruser'])

        LdapUser.objects.create(
            first_name="Foo",
            last_name="User",
            full_name="Foo User",
            group=1000,
            home_directory="/home/foouser",
            uid=2000,
            username="foouser")

        LdapUser.objects.create(
            first_name="Bar",
            last_name="User",
            full_name="Bar User",
            group=1001,
            home_directory="/home/baruser",
            uid=2001,
            username="baruser")

        self.client.login(username="test_user", password="password")

    def test_index(self):
        response = self.client.get('/admin/examples/')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "Ldap users")

    def test_group_list(self):
        response = self.client.get('/admin/examples/ldapgroup/')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

        # order by name
        response = self.client.get('/admin/examples/ldapgroup/?o=1')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

        # order by gid
        response = self.client.get('/admin/examples/ldapgroup/?o=2')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_group_detail(self):
        response = self.client.get('/admin/examples/ldapgroup/foogroup/')
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_group_add(self):
        response = self.client.post('/admin/examples/ldapgroup/add/', {'gid': '1002', 'name': 'wizgroup'})
        self.assertRedirects(response, '/admin/examples/ldapgroup/')
        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 3)

    def test_group_delete(self):
        response = self.client.post('/admin/examples/ldapgroup/foogroup/delete/', {'yes': 'post'})
        self.assertRedirects(response, '/admin/examples/ldapgroup/')
        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 1)

    def test_user_list(self):
        response = self.client.get('/admin/examples/ldapuser/')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

        # order by username
        response = self.client.get('/admin/examples/ldapuser/?o=1')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

        # order by uid
        response = self.client.get('/admin/examples/ldapuser/?o=2')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

    def test_user_detail(self):
        response = self.client.get('/admin/examples/ldapuser/foouser/')
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

    def test_user_delete(self):
        response = self.client.post('/admin/examples/ldapuser/foouser/delete/', {'yes': 'post'})
        self.assertRedirects(response, '/admin/examples/ldapuser/')
