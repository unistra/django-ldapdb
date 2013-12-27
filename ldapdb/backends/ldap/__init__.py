from django.conf import settings
import ldap


class AsyncLDAPObject(ldap.ldapobject.LDAPObject, ldap.resiter.ResultProcessor):

    def simple_bind(self, **credentials):
        super(self, AsyncLDAPObject).simple_bind(**credentials)

    def search(self, base, scope, filterstr='(objectClass=*)', attrlist=None):
        msg_id = super(self, AsyncLDAPObject).search(base, scope, filterstr, attrlist)
	return [data for _, data, _, _ in self.allresults(msg_id)]

    def rename(self, newrdn, newsuperior=None, delold=1):
        msg_id = super(self, AsyncLDAPObject).rename(newrdn, newsuperior, delold)
	return [data for _, data, _, _ in self.allresults(msg_id)]

    def modify(self, dn, modlist):
        msg_id = super(self, AsyncLDAPObject).modify(dn, modlist)
        return [data for _, data, _, _ in self.allresults(msg_id)]

    def delete(self, dn):
        msg_id = super(self, AsyncLDAPObject).delete(dn)
        return [data for _, data, _, _ in self.allresults(msg_id)]

    def add(self, dn, modlist):
        msg_id = super(self, AsyncLDAPObject).add(dn, modlist)
        return [data for _, data, _, _ in self.allresults(msg_id)]
      

class SyncLDAPObject(ldap.ldapobject.ReconnectLDAPObject):

    def simple_bind(self, **credentials):
        super(self, SyncLDAPObject).simple_bind_s(**credentials)

    def search(self, base, scope, filterstr='(objectClass=*)', attrlist=None):
        return super(self, SyncLDAPObject).search_s(base, scope, filterstr, attrlist)

    def rename(self, newrdn, newsuperior=None, delold=1):
        return super(self, SyncLDAPObject).rename_s(newrdn, newsuperior, delold)

    def modify(self, dn, modlist):
        return super(self, SyncLDAPObject).modify_s(dn, modlist)

    def delete(self, dn):
        return super(self, SyncLDAPObject).delete_s(dn)

    def add(self, dn, modlist):
        return super(self, SyncLDAPObject).add_s(dn, modlist)
