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
    error = resp.error()
    data = resp.readAll()
    if error == 0:
        # logger.debug("readResponse: %s", data)
        if len(data) > 0:
            body = bytes(data)
            # FIXME: figure out actual content type
            jsonobj = json.loads(body.decode('utf-8'))
            return jsonobj
    else:
        logger.error('Error: %s', data)


def readLongResponse(resp):
    error = resp.error()
    line = bytes(resp.readLine())
    if error == 0:
        line = line.decode('utf-8').strip()
        if len(line) > 0:
            jsonobj = json.loads(line)
            return jsonobj
    else:
        logger.error('Error: %s', line)
