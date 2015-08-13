from PyQt5.QtNetwork import QNetworkRequest
import json
import logging

logger = logging.getLogger(__name__)


def makeRequest(url, token):
    logger.debug("makeRequest: %s", url)
    req = QNetworkRequest(url)
    req.setRawHeader("Accept", "application/json")
    req.setRawHeader("Authorization", 'Bearer ' + token)
    return req


def readResponse(resp):
    body = bytes(resp.readAll())
    # FIXME: figure out actual content type
    jsonobj = json.loads(body.decode('utf-8'))
    return jsonobj


def readLongResponse(resp):
    line = bytes(resp.readLine())
    line = line.decode('utf-8').strip()
    if len(line) > 0:
        jsonobj = json.loads(line)
        return jsonobj
