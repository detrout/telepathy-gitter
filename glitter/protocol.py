# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2010 Collabora Ltd.
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
import dbus

import telepathy

# import gitter interfaces

from glitter.connection import GlitterConnection

__all__ = ['GlitterProtocol']

logger = logging.getLogger('Glitter.Protocol')

class GlitterProtocol(telepathy.server.Protocol,
                        telepathy.server.ProtocolInterfacePresence):

    _proto = "gitter"
    _vcard_field = ""
    _english_name = "Gitter"
    _icon = "im-msn"

    _secret_parameters = set([
    ])
    _mandatory_parameters = {
        'account': 's',
        'token': 's',
    }
    _optional_parameters = {
    }
    _parameter_defaults = {
    }

    _requestable_channel_classes = [
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_TEXT),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_CONTACT_LIST),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_GROUP)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_CONTACT_LIST),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_LIST)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ]

    _supported_interfaces = [
            telepathy.CONNECTION_INTERFACE_ALIASING,
            telepathy.CONNECTION_INTERFACE_AVATARS,
            telepathy.CONNECTION_INTERFACE_CAPABILITIES,
            telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES,
            telepathy.CONNECTION_INTERFACE_CONTACTS,
            telepathy.CONNECTION_INTERFACE_REQUESTS,
        ]

    _statuses = {
            }


    def __init__(self, connection_manager):
        telepathy.server.Protocol.__init__(self, connection_manager, 'gitter')
        telepathy.server.ProtocolInterfacePresence.__init__(self)

    def create_connection(self, connection_manager, parameters):
        return GlitterConnection(self, connection_manager, parameters)
