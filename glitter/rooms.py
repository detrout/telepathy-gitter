import itertools
import logging

from PyQt5.QtCore import (
    QUrl, QTimer, QObject, pyqtSlot, pyqtSignal
)
from PyQt5.QtNetwork import QNetworkAccessManager
import telepathy

from .grequests import makeRequest, readResponse

logger = logging.getLogger(__name__)

class Rooms(QObject):
    def __init__(self, net, auth, manager):
        QObject.__init__(self)
        self._net = net
        self._auth = auth
        self._manager = manager
        self._rooms = {}

        QTimer().singleShot(0, self.load)

    ready = pyqtSignal()

    def load(self):
        url = QUrl("https://api.gitter.im/v1/rooms/")
        req = makeRequest(url, self._auth)
        self._resp = self._net.get(req)
        self._resp.readyRead.connect(self.readResponse)

    @pyqtSlot()
    def readResponse(self):
        rooms = readResponse(self._resp)
        for room in rooms:
            self._rooms[room['name']] = room
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


class Room(QObject):
    def __init__(self, json=None):
        QObject.__init__(self)

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

    def readJson(self, json):
        for key in ROOM_ATTRIBUTES:
            setattr(self, key, json[key])
        self.ready.emit()

    def __str__(self):
        return self.name


class GitterClient(QObject):
    """Manage a connection to Gitter
    """
    def __init__(self, manager, auth):
        QObject.__init__(self)
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
        self.connected.emit()
        self._rooms.ready.disconnect(self.rooms_initialized)

    def disconnect(self):
        self._refresh_timer.stop()
        self._rooms = None
