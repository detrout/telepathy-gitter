#!/usr/bin/python3
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtNetwork
from PyQt5 import QtWidgets

from pprint import pprint
import sys

token = None
oauth_key = None
oauth_secret = None
# override secret keys in gitter_secret
from .gitter_secret import *

gitter_auth_url = 'https://gitter.im/login/oauth/authorize'

user_id = "55a976b08a7b72f55c3fb897"
encoded_id = "55a976948a7b72f55c3fb894"

def viewresp(response):
    print(response.readLine())

def main():

    app = QtWidgets.QApplication(sys.argv)
    net = QtNetwork.QNetworkAccessManager()
    timer = QtCore.QTimer()
    timer.singleShot(15000, app.quit)

    userapi = "https://api.gitter.im/v1/user"
    roomapi = "https://api.gitter.im/v1/rooms/{}/rooms"
    streamapi = 'https://stream.gitter.im/v1/rooms/{}/chatMessages'
    userurl = QtCore.QUrl(userapi)
    roomsurl = QtCore.QUrl(roomapi.format(user_id))
    encoded = QtCore.QUrl(streamapi.format(encoded_id))
    req = QtNetwork.QNetworkRequest(encoded)
    req.setRawHeader("Accept", "application/json")
    req.setRawHeader("Authorization", 'Bearer '+token)
    resp = net.get(req)
    resp.readyRead.connect(lambda : viewresp(resp))

    app.exec_()
    
if __name__ == '__main__':
    main()

