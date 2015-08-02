#!/usr/bin/python3
from PyQt5.QtCore import (
    QCoreApplication, QUrl, QTimer, QObject,
    pyqtSlot, pyqtSignal
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt5.QtWidgets import QApplication

from pprint import pprint
import sys

token = None
oauth_key = None
oauth_secret = None
# override secret keys in gitter_secret
from secret import *


USER_ATTRIBUTES = [
    'id', 'username', 'displayName', 'url',
    'avatarUrlSmall', 'avatarUrlMedium', 'gv', 'v'
]


class User(QObject):
    def __init__(self, net):
        super(User, self).__init__()
        self._net = net

        self.id = None
        self.username = None
        self.displayName = None
        self.url = None
        self.avatarUrlSmall = None
        self.avatarUrlMedium = None
        self.gv = None
        self.v = None

        self.load()

    def load(self):
        url = QUrl("https://api.gitter.im/v1/user")
        req = makeRequest(url)
        self._resp = self._net.get(req)
        self._resp.readyRead.connect(self.readResponse)

    @pyqtSlot()
    def readResponse(self):
        user = readResponse(self._resp)
        user = user[0]
        for key in USER_ATTRIBUTES:
            if key in user:
                setattr(self, key, user[key])
        print("loaded:", self.id, self.username)
        self.ready.emit()

    ready = pyqtSignal()



class GitterApp(QObject):
    def __init__(self, args):
        super(GitterApp, self).__init__()

        self.app = QApplication(args)
        self.net = QNetworkAccessManager()
        self.timer = QTimer()
        self.timer.singleShot(10000, self.app.quit)

        self.user = User(self.net)
        self.rooms = Rooms(self.net)

    def exec_(self):
        self.app.exec_()


def junk(app):
    userapi = "https://api.gitter.im/v1/user"
    roomapi = "https://api.gitter.im/v1/rooms/{}/rooms"
    streamapi = 'https://stream.gitter.im/v1/rooms/{}/chatMessages'
    
    userurl = QUrl(userapi)
    #roomsurl = QUrl(roomapi.format(user_id))
    #encoded = QUrl(streamapi.format(encoded_id))
    req = QNetworkRequest(userurl)
    req.setRawHeader("Accept", "application/json")
    req.setRawHeader("Authorization", 'Bearer '+token)
    resp = app.net.get(req)
    resp.readyRead.connect(lambda : viewresp(resp))


from telepathy.server.protocol import Protocol
from telepathy.server.channel import ChannelTypeText
from telepathy.server.conn import Connection
from telepathy.server.connmgr import ConnectionManager, _ConnectionManager
from telepathy.server.properties import DBusProperties
from telepathy.interfaces import (
    CONNECTION_INTERFACE_CONTACT_LIST,
    CONN_MGR_INTERFACE
)
import dbus
from dbus.mainloop.pyqt5 import DBusQtMainLoop


class GitterProtocol(Protocol):
    _english_name = "Gitter"
    _icon = ""
    _vcard_field = ""
    _authentication_types = []

    _requestable_channel_classes = [ChannelTypeText]


class GitterConnection(Connection):
    _optional_parameters = {}
    _mandatory_parameters = {}
    _secret_parameters = {}
    _parameter_defaults = {}
    pass


class GitterCM(ConnectionManager):
    def __init__(self):
        """
        Initialise the connection manager.
        """
        name = 'glitter'
        bus_name = 'org.freedesktop.Telepathy.ConnectionManager.%s' % name
        object_path = '/org/freedesktop/Telepathy/ConnectionManager/%s' % name
        _ConnectionManager.__init__(
            self,
            dbus.service.BusName(bus_name, dbus.Bus(), do_not_queue=True),
            object_path)

        self._interfaces = set(CONNECTION_INTERFACE_CONTACT_LIST)
        self._connections = set()
         # proto name => Connection constructor
        self._protos = {'gitter': GitterConnection}
          # proto name => Protocol object
        self._protocols = {'gitter': GitterProtocol}

        DBusProperties.__init__(self)
        self._implement_property_get(CONN_MGR_INTERFACE, {
                'Interfaces': lambda: dbus.Array(self._interfaces, signature='s'),
                'Protocols': lambda: dbus.Dictionary(self._protocol_properties,
                                                     signature='sa{sv}')
                })

        
def test_cm():
    cm = GitterCM()
    print(cm.ListProtocols())

def main():
    #app = GitterApp(sys.argv)
    app = QCoreApplication(sys.argv)
    loop = DBusQtMainLoop(set_as_default=True)
    bus = dbus.SessionBus()

    QTimer().singleShot(0, test_cm)
    QTimer().singleShot(5000, app.quit)

    app.exec_()


if __name__ == '__main__':
    main()
