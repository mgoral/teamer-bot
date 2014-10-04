#!/usr/bin/env python2.7
#-*- coding: utf-8 -*-

# Copyright © 2014 Michal Goral. All Rights Reserved.
#
# This program is free software.
# License: GNU General Public License version 3 or (at your opinion)
#          any later version.
#          See LICENSE for details or <http://www.gnu.org/licenses/>

import os
import sys
import socket
import signal
import logging

from message import Message
import teamerconfig as cfg

log = logging.getLogger('teamer-bot.%s' % __name__)

class Status:
    OK = 0
    INTERRUPT = 1
    CONNECTION_FAILURE = 11
    MESSAGE_TIMEOUT = 12

class ExitWithStatus(Exception):
    status = Status.OK

    def __init__(self, status):
        self.status = status

class Connection:
    def __init__(self):
        self._s = socket.socket()
        self._s.settimeout(cfg.timeout)
        self._connected = False
        self._onChannel = False

    def connect(self):
        self._startConnection()

        if cfg.password is not None:
            self._sendMessage("PASS %s" % cfg.password, True)

        self._sendMessage("NICK %s" % cfg.nick, True)
        self._sendMessage(
            "USER %(username)s %(hostname)s unused-server-name :%(realname)s" %
                {"username" : cfg.ident, "hostname" : cfg.host, "realname" : cfg.realname },
            True)

        log.debug("Connected to %s" % cfg.host)
        self._connected = True

    def quit(self):
        if self._connected is True:
            log.debug("Sending QUIT")
            self._sendMessage("QUIT")
            self._connected = False
            self._onChannel = False

    def joinChannel(self):
        if self._connected is True:
            self._sendMessage("JOIN %s" % cfg.channel, True)

    def run(self):
        self.joinChannel()
        self._s.settimeout(None) # no timeout, blocking mode

        while True:
            msg = self._receiveMessage()
            if msg is not None:
                if msg.command == "PING":
                    self._sendMessage("PONG")
                elif msg.command == "KILL":
                    log.info("Disconnected from a server")
                    self._connected = False
                    self._onChannel = False
                    break # TODO: maybe try to reconnect?
                elif msg.command == "JOIN" and msg.prefix.startswith(cfg.nick):
                    self._onChannel = True
                else:
                    try:
                        if self._onChannel:
                            resps = cfg.messageHandler(msg, log)
                            if resps is not  None:
                                for resp in resps:
                                    # FIXME: add to the queue (prevent flood throttling)
                                    self._sendMessage(self._serializeMessage(resp))
                    except Exception as e:
                        log.debug("Exception occured during custom message handling:")
                        log.debug("  %s" % e)

    def _startConnection(self):
        try:
            self._s.connect((cfg.host, cfg.port))
        except socket.timeout as e:
            log.error("Timeout on connection to %s:%s" % (cfg.host, cfg.port))
            raise ExitWithStatus(Status.CONNECTION_FAILURE)
        except socket.gaierror as (errNo, msg):
            log.error("Cannot resolve a hostname: %s"  % cfg.host)
            log.error(msg)
            raise ExitWithStatus(Status.CONNECTION_FAILURE)

    def _sendMessage(self, msg, critical = False):
        try:
            log.debug(">> %s\r\n" % msg)
            self._s.send("%s\r\n" % msg)
        except socket.timeout as e:
            log.error("Message timeout!")
            log.debug("  %s" % msg)
            if critical is True:
                log.error("It was a critical message! Terminating!")
                raise ExitWithStatus(Status.MESSAGE_TIMEOUT)

    def _receiveMessage(self, bufsize = 4096):
        line = self._s.recv(bufsize)
        log.debug(line)
        return self._parseMessage(line)

    # Shamelessly taken from Twisted Matrix (https://twistedmatrix.com/trac)
    # Licensed under MIT License
    def _parseMessage(self, msg):
        if not msg:
            return None

        prefix = None
        trailing = []

        if msg[0] == ":":
            prefix, msg = msg[1:].split(" ", 1)

        if " :" in msg:
            msg, trailing = msg.split(" :", 1)
            args = msg.split()
            args.append(trailing)
        else:
            args = msg.split()

        command = args.pop(0)
        return Message(prefix, command, args)

    def _serializeMessage(self, msgObj):
        prefix = ""
        command = msgObj.command
        args = ""

        if msgObj.prefix:
            prefix = ":%s " % prefix

        if len(msgObj.args) > 0:
            args, trailing = " ".join(msgObj.args[:-1]), msgObj.args[-1]
            if args != "":
                args = " %s" % args
            if " " in trailing:
                trailing = ":%s" % trailing
            if trailing != "":
                args = "%s %s" % (args, trailing)

        return "%s%s%s" % (prefix, command, args)

class StartConnection:
    def __init__(self):
        self._connection = Connection()

    def __enter__(self):
        self._connection.connect()
        return self._connection

    def __exit__(self, type_, value, traceback):
        self._connection.quit()


def main():
    log.setLevel(logging.DEBUG)
    log.addHandler(logging.StreamHandler())

    botpath = os.path.dirname(__file__)
    os.chdir(botpath)

    with StartConnection() as c:
        c.run()

    return Status.OK

def interruptHandler(signum, frame):
    sys.exit(Status.INTERRUPT) # will spawn atexit

if __name__ == "__main__":
    signal.signal(signal.SIGINT, interruptHandler)

    exitstatus = Status.OK

    try:
        exitstatus = main()
    except ExitWithStatus as e:
        exitstatus = e.status

    sys.exit(exitstatus)

