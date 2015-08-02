# telepathy-glitter - an MSN connection manager for Telepathy
#
# Copyright (C) 2009 Olivier Le Thanh Duong <olivier@lethanh.be>
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
import time

import telepathy
import telepathy.errors
import dbus
from telepathy.constants import (
    CONTACT_LIST_STATE_NONE,
    CONTACT_LIST_STATE_WAITING,
    CONTACT_LIST_STATE_FAILURE,
    CONTACT_LIST_STATE_SUCCESS,

    SUBSCRIPTION_STATE_UNKNOWN,
    SUBSCRIPTION_STATE_NO,
    SUBSCRIPTION_STATE_REMOVED_REMOTELY,
    SUBSCRIPTION_STATE_ASK,
    SUBSCRIPTION_STATE_YES,
    
)

__all__ = ['GlitterContacts']

logger = logging.getLogger('Glitter.Contacts')


class GlitterContacts(
        telepathy.server.ConnectionInterfaceContacts,
        telepathy.server.ConnectionInterfaceContactList,
        telepathy.server.ConnectionInterfaceContactGroups,
        telepathy.server.ConnectionInterfaceContactBlocking,
        telepathy.server.ConnectionInterfaceAliasing,
        telepathy.server.ConnectionInterfaceContactCapabilities,
        #telepathy.server.ConnectionInterfaceSimplePresence,
):
    attributes = {
        telepathy.CONNECTION: 'contact-id',
        telepathy.CONNECTION_INTERFACE_CONTACT_LIST: 'publish',
        telepathy.CONNECTION_INTERFACE_CONTACT_GROUPS: 'groups', 
        telepathy.CONNECTION_INTERFACE_CONTACT_BLOCKING: 'blocked',
        #telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE: 'presence',
        #telepathy.CONNECTION_INTERFACE_ALIASING: 'alias',
        # telepathy.CONNECTION_INTERFACE_AVATARS: 'token',
        # telepathy.CONNECTION_INTERFACE_CAPABILITIES: 'caps',
        telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES: 'capabilities'
        }

    def __init__(self):
        logger.debug("GlitterContacts.__init__")
        telepathy.server.ConnectionInterfaceContacts.__init__(self)
        telepathy.server.ConnectionInterfaceContactList.__init__(self)
        telepathy.server.ConnectionInterfaceContactGroups.__init__(self)
        telepathy.server.ConnectionInterfaceContactBlocking.__init__(self)
        telepathy.server.ConnectionInterfaceAliasing.__init__(self)
        #telepathy.server.ConnectionInterfaceSimplePresence.__init__(self)

        self._implement_property_get(
            telepathy.CONNECTION_INTERFACE_CONTACTS,
            {'ContactAttributeInterfaces':
             self.get_contact_attribute_interfaces,})

        self._implement_property_get(
            telepathy.CONNECTION_INTERFACE_CONTACT_LIST,
            {'ContactListState': lambda: self.contact_list_state,
             'ContactListPersists': lambda: True,
             'CanChangeContactList': lambda: False,
             'RequestUsesMessage': lambda: False,
             'DownloadAtConnection': lambda: True,
            })

        self._implement_property_get(
            telepathy.CONNECTION_INTERFACE_CONTACT_BLOCKING,
            {'ContactBlockingCapabilities': lambda: 0}
        )

        #self._implement_property_get(
        #    telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE,
        #    {'Statuses': ,
        #     'MaximumStatusMessageLength': lambda: 0}
        self._contact_list_state = CONTACT_LIST_STATE_NONE

    def get_contact_attribute_interfaces(self):
        return list(self.attributes.keys())

    def update_handles(self, sender):
        self._contact_handles = self.RequestHandles(
            telepathy.HANDLE_TYPE_CONTACT,
            self._gitter_client._rooms,
            sender=sender)
        state = (SUBSCRIPTION_STATE_YES, SUBSCRIPTION_STATE_YES, '')
        changes = {h: state for h in self._contact_handles}
        identifiers = dict(zip(self._contact_handles,
                               self._gitter_client._rooms))
        removals = {}
        self.contact_list_state = CONTACT_LIST_STATE_SUCCESS
        self.ContactsChangedWithID(changes, identifiers, removals)
        self.ContactsChanged(changes, removals)

    @property
    def contact_list_state(self):
        return self._contact_list_state

    @contact_list_state.setter
    def contact_list_state(self, value):
        if value != self._contact_list_state:
            self._contact_list_state = value
            self.ContactListStateChanged(value)

    @dbus.service.signal(dbus_interface=telepathy.CONNECTION_INTERFACE_CONTACTS,
                         signature='u')
    def ContactListStateChanged(self, value):
        logger.debug("ContactListStateChanged to: %d", value)

    def GetSubscription(self, handle_type, handles):
        logger.debug("GetSubscription: %s", str(handles))
        return [SUBSCRIPTION_STATE_YES for h in handles]

    @dbus.service.method(
        dbus_interface=telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES,
        in_signature="au",
        out_signature="a{ua(a{sv}as)}")
    def GetContactCapabilities(self, handles):
        logger.debug("GetContactCapabilities: %s", str(handles))
        handles = set(handles)
        if 0 in handles:
            handles.remove(0)
            
        ret = dbus.Dictionary(signature="ua(a{sv}as)")
        channels = dbus.Dictionary(signature="sv")
        channels['org.freedesktop.Telepathy.Channel.TargetHandleType'] = 1
        channels['org.freedesktop.Telepathy.Channel.ChannelType'] = \
             'org.freedesktop.Telepathy.Channel.Type.Text'                                                       
        interfaces = dbus.Array(['org.freedesktop.Telepathy.Channel.TargetHandle'], signature="s")
        for h in handles:
            ret[int(h)] = dbus.Struct([ channels, interfaces ], signature="(a{sv}as)")

        return ret

    ### Start Contacts
    # Overwrite the dbus attribute to get the sender argument
    @dbus.service.method(telepathy.CONNECTION_INTERFACE_CONTACTS,
                         in_signature='auasb',
                         out_signature='a{ua{sv}}',
                         sender_keyword='sender')
    def GetContactAttributes(self, handles, interfaces, hold, sender):
        logger.debug("GetContactAttributes: %s, %s",
                     ', '.join((str(x) for x in handles)),
                     ', '.join(interfaces))
        # InspectHandle already checks we're connected, the handles and handle type.
        supported_interfaces = set()
        for interface in interfaces:
            if interface in self.attributes:
                supported_interfaces.add(interface)
            else:
                logger.debug("Ignoring unsupported interface %s" % interface)

        handle_type = telepathy.HANDLE_TYPE_CONTACT
        ret = dbus.Dictionary(signature='ua{sv}')
        for handle in handles:
            ret[handle] = dbus.Dictionary(signature='sv')

        functions = {
            telepathy.CONNECTION:
                lambda x: zip(x, self.InspectHandles(handle_type, x)),
            telepathy.CONNECTION_INTERFACE_CONTACT_LIST:
                lambda x: zip(x, self.GetSubscription(handle_type, x)),
            telepathy.CONNECTION_INTERFACE_CONTACT_GROUPS:
                lambda x: zip(x, self.GetContactGroups(handle_type, x)),
            telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE:
                lambda x: self.GetPresences(x).items(),
            telepathy.CONNECTION_INTERFACE_ALIASING:
                lambda x: self.GetAliases(x).items(),
            telepathy.CONNECTION_INTERFACE_AVATARS:
                lambda x: self.GetKnownAvatarTokens(x).items(),
            telepathy.CONNECTION_INTERFACE_CAPABILITIES:
                lambda x: self.GetCapabilities(x).items(),
            telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES:
                lambda x: self.GetContactCapabilities(x).items()
            }

        #Hold handles if needed
        if hold:
            self.HoldHandles(handle_type, handles, sender)

        # Attributes from the interface org.freedesktop.Telepathy.Connection
        # are always returned, and need not be requested explicitly.
        supported_interfaces.add(telepathy.CONNECTION)

        for interface in supported_interfaces:
            logger.debug("Inspecting %s", interface)
            interface_attribute = interface + '/' + self.attributes[interface]
            interface_subscribe = interface + '/' + 'subscribe'
            results = functions[interface](handles)
            for handle, value in results:
                ret[int(handle)][interface_attribute] = value
                if self.attributes[interface] == 'publish':
                    ret[int(handle)][interface_subscribe] = value

        return ret

    @dbus.service.method(telepathy.CONNECTION_INTERFACE_CONTACTS,
                         in_signature='sas',
                         out_signature='ua{sv}',
                         sender_keyword='sender')
    def GetContactByID(self, identifier, interfaces, sender):
        logger.debug("%s %s", identifier, ', '.join(interfaces))
        contacts = self.GetContactAttributes([identifier], interfaces, sender)
        return contacts[identifier]
    # End Contacts

    # Start Request
    # End Request
    
    # Start ContactList
    @dbus.service.method(telepathy.CONNECTION_INTERFACE_CONTACT_LIST,
                         in_signature='asb',
                         out_signature='a{ua{sv}}',
                         sender_keyword='sender',
    )
    def GetContactListAttributes(self, interfaces, hold, sender):
        logger.debug('GetContactListAttributes: %s', ', '.join(interfaces))
        self.check_connected()
        interfaces = set(interfaces)
        interfaces.add(telepathy.CONNECTION_INTERFACE_CONTACT_LIST)
        return self.GetContactAttributes(
            self._contact_handles, interfaces, hold, sender)
    # End ContactList

    ### Start ContactGroups

    def GetContactGroups(self, handle_type, handles):
        return [ [] for h in handles ] 
            
    ### End ContactGroups
    ### Start ContactBlocking
    @dbus.service.method(telepathy.CONNECTION_INTERFACE_CONTACT_BLOCKING,
                         in_signature='',
                         out_signature='a{us}')
    def RequestBlockedContacts(self):
        return {}

    ### End ContactBlocking

    ### Start Aliasing interface
    def GetAliasFlags(self):
        logger.debug("GetAliasFlags")
        return 0

    def GetAliases(self, contacts):
        logger.debug("GetAliases")
        ret = dbus.Dictionary(singnature="a{us}")
        return ret

    ### End Aliasing interface
