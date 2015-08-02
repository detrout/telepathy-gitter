# telepathy-glitter - an MSN connection manager for Telepathy
#
# Copyright (C) 2007 Ali Sabil <ali.sabil@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import logging
import weakref

import telepathy

__all__ = ['GlitterHandleFactory', ]

logger = logging.getLogger('Glitter.Handle')


def GlitterHandleFactory(connection, type, id, name, **kwargs):
    mapping = {telepathy.HANDLE_TYPE_CONTACT: GlitterContactHandle,
               telepathy.HANDLE_TYPE_LIST: GlitterListHandle,
               telepathy.HANDLE_TYPE_GROUP: GlitterGroupHandle}
    handle = mapping[type](connection, id, name, **kwargs)
    connection._handles[handle.type, handle.id] = handle
    return handle


class GlitterHandle(telepathy.server.Handle):
    def __init__(self, connection, id, handle_type, name):
        telepathy.server.Handle.__init__(self, id, handle_type, name)
        self._conn = weakref.proxy(connection)

    def __str__(self):
        type_mapping = {telepathy.HANDLE_TYPE_CONTACT : 'Contact',
                telepathy.HANDLE_TYPE_ROOM : 'Room',
                telepathy.HANDLE_TYPE_LIST : 'List',
                telepathy.HANDLE_TYPE_GROUP : 'Group'}
        type_str = type_mapping.get(self.type, '')
        return "<Glitter%sHandle id=%u name='%s'>" % \
            (type_str, self.id, self.name)


class GlitterContactHandle(GlitterHandle):
    def __init__(self, connection, id, contact_name, contact=None):
        handle_type = telepathy.HANDLE_TYPE_CONTACT
        handle_name = contact_name
        self._contact = contact

        if contact is None:
            contact_account = contact_name.lower()
            contact_network = papyon.NetworkID.MSN
            for network, extension in network_to_extension.items():
                if contact_name.endswith(extension):
                    contact_account = contact_name[0:-len(extension)]
                    contact_network = network
                    break
        else:
            contact_account = contact.account
            contact_network = contact.network_id

        self.account = contact_account
        self.network = contact_network
        self.pending_groups = set()
        self.pending_alias = None
        GlitterHandle.__init__(self, connection, id, handle_type, handle_name)

    @property
    def contact(self):
        if self._contact is None:
            if self.account == self._conn._msn_client.profile.account.lower() and \
                    self.network == papyon.NetworkID.MSN:
                self._contact = self._conn.msn_client.profile
            else:
                self._contact = self._conn.msn_client.address_book.search_contact(
                        self.account, self.network)
        return self._contact


class GlitterListHandle(GlitterHandle):
    def __init__(self, connection, id, list_name):
        handle_type = telepathy.HANDLE_TYPE_LIST
        handle_name = list_name
        GlitterHandle.__init__(self, connection, id, handle_type, handle_name)


class GlitterGroupHandle(GlitterHandle):
    def __init__(self, connection, id, group_name):
        handle_type = telepathy.HANDLE_TYPE_GROUP
        handle_name = group_name
        GlitterHandle.__init__(self, connection, id, handle_type, handle_name)

    @property
    def group(self):
        for group in self._conn.msn_client.address_book.groups:
            # Microsoft seems to like case insensitive stuff
            if group.name.decode("utf-8").lower() == self.name.lower():
                return group
        return None
