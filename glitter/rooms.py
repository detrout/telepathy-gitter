import configparser
import logging
import os
from pprint import pformat
import datetime
import json
import collections
import pytz

from PyQt5.QtCore import (
    QUrl, QUrlQuery, QTimer, QObject, pyqtSlot, pyqtSignal, QStandardPaths
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from .grequests import makeRequest, readResponse, readLongResponse

logger = logging.getLogger(__name__)

GITTER_SERVER = 'gitter.im'
API_VERSION = '/v1/'
GITTER_API = 'https://api.' + GITTER_SERVER + API_VERSION
GITTER_STREAM = 'https://stream.' + GITTER_SERVER + API_VERSION

class GitterObject(QObject):
    def __init__(self):
        super().__init__()

    def safesetattr(self, name, value):
        """Only set self.name=value for non-private attributes
        """
        if not name.startswith('_') and name in self.__dict__:
            setattr(self, name, value)


class Rooms(GitterObject):
    def __init__(self, net, auth, manager):
        super().__init__()
        self._net = net
        self._auth = auth.encode('utf-8')
        self._manager = manager
        self._rooms = {}

        QTimer().singleShot(0, self.load)

    ready = pyqtSignal()

    def load(self):
        logger.debug("load %d", len(self._rooms))
        url = QUrl(GITTER_API + "rooms/")
        req = makeRequest(url, self._auth)
        resp = self._net.get(req)
        resp.readyRead.connect(lambda: self.readResponse(resp))

    @pyqtSlot()
    def readResponse(self, resp):
        rooms = readResponse(resp)
        for roomjson in rooms:
            name = roomjson['name']
            if name in self._rooms:
                # update attributes
                self._rooms[name].readJson(roomjson)
            else:
                # create new room
                self._rooms[name] = Room(self._net, self._auth, json=roomjson)
            logger.debug('Room: %s %d messages',
                         name,
                         len(self._rooms[name].messages))
        self.ready.emit()

    def disconnect(self):
        for room in self._rooms:
            self._rooms[room].disconnect()

    # mapping interface
    def __getitem__(self, key):
        return self._rooms[key]

    def __iter__(self):
        return iter(self._rooms)

    def __len__(self):
        return len(self._rooms)

    def __contains__(self, key):
        return key in self._rooms

    def keys(self):
        return self._rooms.keys()

    def items(self):
        return self._rooms.items()

    def values(self):
        return self._rooms.values()

    def get(self, key, value=None):
        return self.get(key, value)

    def __eq__(self, other):
        return self._rooms == other

    def __ne__(self, other):
        return self._rooms != other


ROOM_ATTRIBUTES = ['id', 'name', 'topic', 'uri', 'oneToOne',
                   'users', 'userCount', 'unreadItems', 'mentions',
                   'lastAccessTime', 'lurk', 'url', 'githubType', 'v']


class Room(GitterObject):
    __last_message_attribute = 'last_message_id'

    def __init__(self, net, auth, json=None):
        super().__init__()
        self._net = net
        self._auth = auth
        self._messages = Messages(self)
        self._events = None

        self.id = None
        self.name = None
        self.topic = None
        self.uri = None
        self.oneToOne = None
        self.users = None
        self.userCount = None
        self.unreadItems = None
        self.mentions = None
        self.lastAccessTime = None
        self.lurk = None
        self.url = None
        self.githubType = None
        self.v = None

        if json:
            self.readJson(json)

        if len(self._messages) == 0:
            self.loadLastMessageId()

    ready = pyqtSignal()
    messagesReceived = pyqtSignal(str)
    messageSent = pyqtSignal(str)
    newEarliestMessage = pyqtSignal(str)
    newLatestMessage = pyqtSignal(str)

    @property
    def config(self):
        """Return an initialized config parser
        """
        config = configparser.ConfigParser()
        if os.path.exists(self.configFilename):
            config.read([self.configFilename])
        return config

    @property
    def configFilename(self):
        datapath = QStandardPaths.writableLocation(QStandardPaths.DataLocation)
        filename = os.path.join(datapath, 'glitter.ini')
        return filename

    def readJson(self, json):
        for key in json:
            self.safesetattr(key, json[key])
        self.ready.emit()

    def __str__(self):
        return self.name

    def loadLastMessageId(self):
        config = self.config
        if self.name in config:
            return config[self.name][self.__last_message_attribute]

    def saveLastMessageId(self):
        config = self.config
        last_id = self.messages.last_id
        logger.debug("saving last id: %s", last_id)
        if last_id:
            config[self.name][self.__last_message_attribute] = last_id
        with open(self.configFilename, 'wt') as outstream:
            config.write(outstream)

    def loadMessages(self, skip=None, beforeId=None, afterId=None, limit=50):
        logger.debug("listMessages")
        url = QUrl(
            GITTER_API + "/rooms/{}/chatMessages".format(self.id)
        )
        query = QUrlQuery()
        if skip:
            query.addQueryItem("skip", str(skip))
        if beforeId:
            query.addQueryItem("beforeId", str(beforeId))
        if afterId:
            query.addQueryItem("afterId", str(afterId))
        elif self._messages.last_id:
            query.addQueryItem("afterId", str(self._messages.last_id()))
        if limit:
            query.addQueryItem("limit", str(limit))

        url.setQuery(query)
        req = makeRequest(url, self._auth)
        reply = self._net.get(req)
        reply.finished.connect(lambda: self.readMessages(reply))

    @pyqtSlot()
    def readMessages(self, reply):
        messages = readResponse(reply)
        if messages:
            new_messages = []
            for json_message in messages:
                message = Message(json=json_message)
                if message.id not in self._messages:
                    self._messages[message.id] = message
                    new_messages.append(message.id)
            self.messagesReceived.emit(new_messages)

    def startMessageStream(self):
        """Open a socket to this room and listen for events
        """
        logger.debug("startMessageStream")
        url = QUrl(
            GITTER_STREAM + "rooms/{}/chatMessages".format(self.id)
        )
        req = makeRequest(url, self._auth)
        self._events = self._net.get(req)
        self._events.readyRead.connect(
            lambda: self.receiveMessageStream(self._events))
        self._events.finished.connect(self.startMessageStream)

    def receiveMessageStream(self, response):
        """Receive an event from the socket
        """
        json_message = readLongResponse(response)
        if json_message:
            logger.debug('receiveMessage: %s', pformat(json_message))
            message = Message(json=json_message)
            if message.id not in self._messages:
                self._messages[message.id] = message
                self.messagesReceived.emit(message.id)

    def disconnect(self):
        logger.debug("disconnect")
        if isinstance(self._events, QNetworkRequest):
            self._events.abort()
            self._events.finished.disconnect(self.startEventStream)
        self.saveLastMessageId()

    def sendMessage(self, text):
        url = QUrl(
            GITTER_API + "rooms/{}/chatMessages".format(self.id)
        )
        body = {'text': text}
        message = json.dumps(body)
        logger.debug('sendMessage: %s', message)
        req = makeRequest(url, self._auth)
        req.setRawHeader('Content-Type', 'application/json')
        reply = self._net.post(req, message)
        reply.finished.connect(lambda: self.sentMessage(reply))

    @pyqtSlot()
    def sentMessage(self, reply):
        data = readResponse(reply)
        if data:
            message = Message(json=data)
            self._messages[message.id] = message
            self.messageSent.emit(message.id)

    @property
    def messages(self):
        return self._messages


class Messages(collections.MutableMapping):
    def __init__(self, room):
        super().__init__()
        self._room = room
        self._messages = collections.OrderedDict()
        self._earliest_timestamp = None
        self._earliest_id = None
        self._latest_timestamp = None
        self._latest_id = None

    def __getitem__(self, key):
        return self._messages[key]

    def __setitem__(self, key, value):
        if not isinstance(value, Message):
            raise ValueError("We only store Messages")
        if self._latest_id is None or value.sent_timestamp > self._latest_timestamp:
            self._latest_id = value.id
            self._room.newLatestMessage.emit(self._latest_id)
        if self._earliest_id is None or value.sent_timestamp < self._earliest_timestamp:
            self._earliest_id = value.id
            self._room.newEarliestMessage.emit(self._earliest_id)
        self._messages[key] = value

    def __delitem__(self, key):
        del self._messages[key]

    def __iter__(self):
        return iter(self._messages)

    def __len__(self):
        return len(self._messages)

    @property
    def last_id(self):
        return self._latest_id

    @property
    def earliest_id(self):
        return self._earliest_id


class Message(GitterObject):
    def __init__(self, json=None):
        super().__init__()

        self.id = None
        self.text = None
        self.html = None
        self.sent = None
        self.editedAt = None
        self.fromUser = None
        self.unread = None
        self.readBy = None
        self.urls = None
        self.mentions = None
        self.issues = None
        self.meta = None
        self.v = None

        if json:
            self.loadJson(json)

    ready = pyqtSignal()

    def loadJson(self, json):
        isoformat = "%Y-%m-%dT%H:%M:%S.%fZ"
        utc = pytz.timezone('UTC')
        for key in json:
            value = json[key]
            if key in ('sent', 'editedAt') and value is not None:
                value = datetime.datetime.strptime(value, isoformat)
                value = utc.localize(value)
            self.safesetattr(key, value)
        self.ready.emit()
        print(self.sent, self.text)

    @property
    def sent_timestamp(self):
        if self.sent:
            return int(self.sent.timestamp())


class GitterClient(QObject):
    """Manage a connection to Gitter
    """
    def __init__(self, manager, auth):
        super().__init__()
        self._manager = manager
        self._auth = auth
        self._rooms = None
        self._net = QNetworkAccessManager()
        self._rooms = None
        self._user = None
        self._refresh_timer = None

    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def connect(self):
        if self._refresh_timer is None:
            self._refresh_timer = QTimer()
            self._refresh_timer.timeout.connect(self.refresh_client)

        if not self._refresh_timer.isActive():
            self._rooms = Rooms(self._net, self._auth, self._manager)
            self._rooms.ready.connect(self.rooms_initialized)
            self._refresh_timer.start(600000)

    def refresh_client(self):
        # really should check to see if changed?
        self._rooms.load()

    def rooms_initialized(self):
        logger.debug("rooms initialized")
        self.connected.emit()
        self._rooms.ready.disconnect(self.rooms_initialized)

    def disconnect(self):
        self._refresh_timer.stop()
        self._rooms.disconnect()

    @property
    def rooms(self):
        return self._rooms
