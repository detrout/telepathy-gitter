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
import weakref

import dbus
import telepathy
import itertools

from telepathy._generated.Channel_Interface_Messages import ChannelInterfaceMessages
from telepathy.interfaces import CHANNEL_INTERFACE_MESSAGES

from glitter.channel import GlitterChannel

__all__ = ['GlitterTextChannel']

logger = logging.getLogger('Glitter.TextChannel')


class GlitterTextChannel(
        GlitterChannel,
        telepathy.server.ChannelTypeText,
        ChannelInterfaceMessages,
):
    def __init__(self, conn, manager, room, props, object_path=None):
        logger.debug("GlitterTextChannel: %s", room)
        for k in props:
            logger.debug("GlitterTextChannel: %s: %s", k, props[k])
        self._recv_id = 0
        self._conn_ref = weakref.ref(conn)
        self._room = room
        self._room.messageSent.connect(self._signal_text_sent)
        self._room.messagesReceived.connect(self._signal_text_received)
        self._pending_counter = itertools.count()
        self._room.startMessageStream()

        telepathy.server.ChannelTypeText.__init__(
            self, conn, manager, props,
            object_path=object_path)
        self._message_types.append(telepathy.CHANNEL_TEXT_MESSAGE_TYPE_ACTION)
        logger.debug("trying to set %s", telepathy.CHANNEL_INTERFACE_MESSAGES + '.MessageTypes')
        props[telepathy.CHANNEL_INTERFACE_MESSAGES + '.MessageTypes'] = self.GetMessageTypes()
        GlitterChannel.__init__(self, conn, props)
        ChannelInterfaceMessages.__init__(self)

        self._implement_property_get(CHANNEL_INTERFACE_MESSAGES, {
            'SupportedContentTypes': lambda: ['text/plain'], #, 'text/html'],
            'MessageTypes': self.GetMessageTypes,
            'MessagePartSupportFlags': lambda: 0,
            'PendingMessages': lambda: dbus.Array(
                self._pending_messages.values(),
                signature='aa{sv}'),
            'DeliveryReportingSupport': lambda: (
                telepathy.DELIVERY_REPORTING_SUPPORT_FLAG_RECEIVE_FAILURES |
                telepathy.DELIVERY_REPORTING_SUPPORT_FLAG_RECEIVE_SUCCESSES |
                telepathy.DELIVERY_REPORTING_SUPPORT_FLAG_RECEIVE_READ
            )
        })

        self._add_immutables({
            'SupportedContentTypes': CHANNEL_INTERFACE_MESSAGES,
            'MessageTypes': CHANNEL_INTERFACE_MESSAGES,
            'MessagePartSupportFlags': CHANNEL_INTERFACE_MESSAGES,
            'DeliveryReportingSupport': CHANNEL_INTERFACE_MESSAGES,
            })

    def get_participants(self):
        if self._room:
            return self._room.users
        else:
            return set()

    def _signal_text_sent(self, message_id):
        logger.debug("_signal-text-sent: %s", message_id)
        message = self._room.messages[message_id]
        message_type = telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL
        headers = {'message-sent': message.sent_timestamp,
                   'message-type': message_type}
        plain = {'content-type': 'text/plain',
                 'content': message.text}
        html = {'content-type': 'text/html',
                'content': message.html}
        self.Sent(message.sent_timestamp, message_type, message.text)
        self.MessageSent([headers, plain, html], 0, '')

    def _signal_text_received(self, message_id):
        logger.debug("_signal_text_received: %s", str(message_id))
        message_type = telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL
        pending_id = next(self._pending_counter)
        message = self._room.messages[message_id]

        headers = dbus.Dictionary({
            'message-received': dbus.UInt64(message.sent_timestamp),
            'pending-message-id': pending_id,
            'message-sender': 0,
            'message-type': telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL,
            'sender-nickname': message.fromUser['username'],
        }, signature='sv')
        plain = dbus.Dictionary({
            'content-type': 'text/plain',
            'content': message.text
        }, signature='sv')
        html = dbus.Dictionary({
            'content-type': 'text/html',
            'content': message.html
        }, signature='sv')
        message_parts = dbus.Array([headers, plain, html],
                                   signature='a{sv}')

        self.Received(pending_id,
                      message.sent_timestamp,
                      0,
                      message_type,
                      0, message.text)
        self.MessageReceived(message_parts)

    @dbus.service.method(telepathy.CHANNEL_TYPE_TEXT,
                         in_signature='us',
                         out_signature='',
                         async_callbacks=('_success', '_error'))
    def Send(self, message_type, text, _success, _error):
        raise NotImplemented()

    def Close(self):
        logger.debug("Close")
        if self._room is not None:
            self._room.disconnect()
        telepathy.server.ChannelTypeText.Close(self)

    def GetPendingMessageContent(self, message_id, parts):
        # We don't support pending message
        raise telepathy.InvalidArgument()

    @dbus.service.method(telepathy.CHANNEL_INTERFACE_MESSAGES,
                         in_signature='aa{sv}u',
                         out_signature='s',
                         async_callbacks=('_success', '_error'))
    def SendMessage(self, message, flags, _success, _error):
        headers = message.pop(0)
        message_type = int(headers.get('message-type', telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL))
        if message_type != telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL:
                raise telepathy.NotImplemented("Unhandled message type")
        text = None
        for part in message:
            if part.get("content-type", None) == "text/plain":
                text = part['content']
                break
        if text is None:
                raise telepathy.NotImplemented("Unhandled message type")

        self._room.sendMessage(text)
        _success('')

    # Redefine GetSelfHandle since we use our own handle
    #  as Glitter doesn't have channel specific handles
    def GetSelfHandle(self):
        return self._conn.GetSelfHandle()

    @dbus.service.signal(telepathy.CHANNEL_INTERFACE_MESSAGES,
                         signature='aa{sv}')
    def MessageReceived(self, message):
        logger.debug("MessageReceived: %s", message)
        pass
