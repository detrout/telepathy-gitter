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
    body = bytes(resp.readLine())
    # FIXME: figure out actual content type
    jsonobj = json.loads(body.decode('utf-8'))
    return jsonobj
