# telepathy-glitter - an MSN connection manager for Telepathy
#
# Copyright (C) 2006-2007 Ali Sabil <ali.sabil@gmail.com>
# Copyright (C) 2007 Johann Prieur <johann.prieur@gmail.com>
# Copyright (C) 2009-2010 Collabora, Ltd.
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

import telepathy

from glitter.util.decorator import async
from glitter.channel.text import GlitterTextChannel

__all__ = ['GlitterMucChannel']

logger = logging.getLogger('Glitter.MucChannel')


class GlitterMucChannel(
        GlitterTextChannel,
        telepathy.server.ChannelInterfaceGroup):

    def __init__(self, conn, manager, room, props, object_path=None):
        GlitterTextChannel.__init__(self, conn, manager, room, props, object_path)
        telepathy.server.ChannelInterfaceGroup.__init__(self)

        self.GroupFlagsChanged(
            telepathy.CHANNEL_GROUP_FLAG_CHANNEL_SPECIFIC_HANDLES |
            telepathy.CHANNEL_GROUP_FLAG_HANDLE_OWNERS_NOT_AVAILABLE,
            0
        )

        # This is done in an idle so that classes which subclass this one
        # can do stuff in their __init__ but will still benefit from this method
        # being called.
        self.__add_initial_participants()

    def RemoveMembers(self, contacts, message):
        # Group interface, only removing ourself is supported
        if int(self._conn.self_handle) in contacts:
            self.Close()
        else:
            raise telepathy.PermissionDenied()

    def on_room_user_joined(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        logger.info("User %s joined" % str(handle))

        if handle not in self._members:
            self.MembersChanged(
                '', [handle], [], [], [],
                handle, telepathy.CHANNEL_GROUP_CHANGE_REASON_INVITED)

    def on_room_user_left(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        logger.info("User %s left" % str(handle))

        self.MembersChanged(
            '', [], [handle], [], [],
            handle, telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)

    def AddMembers(self, contacts, message):
        raise telepathy.PermissionDenied("We can't add members")

    @async
    def __add_initial_participants(self):
        handles = []
        handles.append(self._conn.self_handle)
        if self._room:
            for user in self._room.users:
                name = user['username']
                # FIXME: This sender is a hack to make a room specific handle
                handle = self._conn.ensureContactHandle(name, sender=self._object_path)
                handles.append(handle)

        if handles:
            self.MembersChanged('', handles, [], [], [],
                    0, telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)
