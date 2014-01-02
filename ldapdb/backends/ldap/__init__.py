import ldap
import ldap.resiter
from ldap.ldapobject import LDAPObject, ReconnectLDAPObject


class AsyncLDAPObject(LDAPObject, ldap.resiter.ResultProcessor):

    def bind(self, **credentials):
        LDAPObject.simple_bind(self, **credentials)

    def search(self, base, scope, filterstr='(objectClass=*)', attrlist=None):
        msg_id = LDAPObject.search(self, base, scope, filterstr, attrlist)
	return [data for _, data, _, _ in self.allresults(msg_id)]

    def rename(self, newrdn, newsuperior=None, delold=1):
        msg_id = LDAPObject.rename(self, newrdn, newsuperior, delold)
	return [data for _, data, _, _ in self.allresults(msg_id)]

    def modify(self, dn, modlist):
        msg_id = LDAPObject.modify(self, dn, modlist)
        return [data for _, data, _, _ in self.allresults(msg_id)]

    def delete(self, dn):
        msg_id = LDAPObject.delete(self, dn)
        return [data for _, data, _, _ in self.allresults(msg_id)]

    def add(self, dn, modlist):
        msg_id = LDAPObject.add(self, dn, modlist)
        return [data for _, data, _, _ in self.allresults(msg_id)]
      

class SyncLDAPObject(ReconnectLDAPObject):

    def bind(self, **credentials):
        ReconnectLDAPObject.simple_bind_s(self, **credentials)

    def search(self, base, scope, filterstr='(objectClass=*)', attrlist=None):
        return ReconnectLDAPObject.search_s(self, base, scope, filterstr, 
                                            attrlist)

    def rename(self, newrdn, newsuperior=None, delold=1):
        return ReconnectLDAPObject.rename_s(self, newrdn, newsuperior, delold)

    def modify(self, dn, modlist):
        return ReconnectLDAPObject.modify_s(self, dn, modlist)

    def delete(self, dn):
        return ReconnectLDAPObject.delete_s(self, dn)

    def add(self, dn, modlist):
        return ReconnectLDAPObject.add_s(self, dn, modlist)
