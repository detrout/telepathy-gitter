import itertools
import logging
from pprint import pformat
from PyQt5.QtCore import (
    QUrl, QUrlQuery, QTimer, QObject, pyqtSlot, pyqtSignal
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
import telepathy

from .grequests import makeRequest, readResponse, readLongResponse

logger = logging.getLogger(__name__)


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
        self._auth = auth
        self._manager = manager
        self._rooms = {}

        QTimer().singleShot(0, self.load)

    ready = pyqtSignal()

    def load(self):
        logger.debug("load")
        url = QUrl("https://api.gitter.im/v1/rooms/")
        req = makeRequest(url, self._auth)
        resp = self._net.get(req)
        resp.readyRead.connect(lambda: self.readResponse(resp))

    @pyqtSlot()
    def readResponse(self, resp):
        rooms = readResponse(resp)
        for room in rooms:
            self._rooms[room['name']] = Room(self._net, self._auth, json=room)
        self.ready.emit()

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
    def __init__(self, net, auth, json=None):
        super().__init__()
        self._net = net
        self._auth = auth
        self._messages = {}
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

    ready = pyqtSignal()
    messagesReady = pyqtSignal([int])

    def readJson(self, json):
        for key in json:
            self.safesetattr(key, json[key])
        self.ready.emit()

    def __str__(self):
        return self.name

    def loadMessages(self, skip=None, beforeId=None, afterId=None, limit=50):
        logger.debug("listMessages")
        url = QUrl(
            "https://api.gitter.im/v1/rooms/{}/chatMessages".format(self.id)
        )
        query = QUrlQuery()
        if skip:
            query.addQueryItem("skip", str(skip))
        if beforeId:
            query.addQueryItem("beforeId", str(beforeId))
        if afterId:
            query.addQueryItem("afterId", str(afterId))
        if limit:
            query.addQueryItem("limit", str(limit))

        url.setQuery(query)
        req = makeRequest(url, self._auth)
        resp = self._net.get(req)
        resp.finished.connect(lambda: self.readMessages(resp))

    @pyqtSlot()
    def readMessages(self, resp):
        messages = readResponse(resp)
        new_messages = []
        for json_message in messages:
            message = Message(json=json_message)
            self._messages[message.id] = message
            new_messages.append(message.id)
        self.messagesReady.emit(new_messages)

    def startMessageStream(self):
        """Open a socket to this room and listen for events
        """
        logger.debug("startMessageStream")
        url = QUrl(
            "https://stream.gitter.im/v1/rooms/{}/chatMessages".format(self.id)
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
        logger.debug('receiveEvent: %s', pformat(json_message))
        if json_message:
            message = Message(json=json_message)
            self._messages[message.id] = message

    def closeMessageStream(self):
        if isinstance(self._events, QNetworkRequest):
            self._events.finished.disconnect(self.startEventStream)

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
        for key in json:
            self.safesetattr(key, json[key])
        self.ready.emit()
        print(self.sent, self.text)

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
        self._rooms = None

    @property
    def rooms(self):
        return self._rooms
