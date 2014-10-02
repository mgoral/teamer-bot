#!/usr/bin/env python2
#-*- coding: utf-8 -*-

# Copyright © 2014 Michal Goral. All Rights Reserved.
#
# This program is free software.
# License: GNU General Public License version 3 or (at your opinion)
#          any later version.
#          See LICENSE for details or <http://www.gnu.org/licenses/>

import sys
import socket
import signal
import logging

log = logging.getLogger('teamer-bot.%s' % __name__)

version = 0.1
HELP_MSG = [
        "BBConf Teamer bot, version: %s" % version,
        "Currently I'm only idling and saying bullshit. ;)"
    ]

class Status:
    OK = 0
    INTERRUPT = 1
    CONNECTION_FAILURE = 11
    MESSAGE_TIMEOUT = 12

class ExitWithStatus(Exception):
    status = Status.OK

    def __init__(self, status):
        self.status = status

class Message:
    """Merely a wrapper for 3 named fields."""
    def __init__(self, prefix = "", command = "", args = []):
        self.prefix = prefix
        self.command = command
        self.args = args

class Connection:
    PASS = None                 # connection password. Won't be used if None
    HOST = "chat.freenode.net"  # server address
    PORT = 6667                 # server port (int)
    CHANNEL = "#bbconf"         # default channel to connect

    IDENT = "bbconf-teamer"     # bot username
    NICK = "teamer"             # bot nicknakme
    REALNAME = "BBConf Teamer"  # bot realname (might contain spaces)
    OWNER = "virgoerns"         # nickname of bot owner

    CONN_TIMEOUT = 30.0         # timeout (in seconds) for connection and messages

    def __init__(self):
        self._s = socket.socket()
        self._s.settimeout(self.CONN_TIMEOUT)
        self._connected = False

    def connect(self):
        self._startConnection()

        if self.PASS is not None:
            self._sendMessage("PASS %s" % self.PASS, True)

        self._sendMessage("NICK %s" % self.NICK, True)
        self._sendMessage(
            "USER %(username)s %(hostname)s unused-server-name :%(realname)s" %
                {"username" : self.IDENT, "hostname" : self.HOST, "realname" : self.REALNAME },
            True)

        log.debug("Connected to %s" % self.HOST)
        self._connected = True

    def quit(self):
        if self._connected is True:
            log.debug("Sending QUIT")
            self._sendMessage("QUIT")

    def joinChannel(self):
        if self._connected is True:
            self._sendMessage("JOIN %s" % self.CHANNEL, True)

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
                    break # TODO: maybe try to reconnect?
                elif msg.command == "PRIVMSG":
                    self._handlePrivMsg(msg)

    def _startConnection(self):
        try:
            self._s.connect((self.HOST, self.PORT))
        except socket.timeout as e:
            log.error("Timeout on connection to %s:%s" % (self.HOST, self.PORT))
            raise ExitWithStatus(Status.CONNECTION_FAILURE)
        except socket.gaierror as (errNo, msg):
            log.error("Cannot resolve a hostname: %s"  % self.HOST)
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

        if msg.find(" :") != -1:
            msg, trailing = msg.split(" :", 1)
            args = msg.split()
            args.append(trailing)
        else:
            args = msg.split()

        command = args.pop(0)
        return Message(prefix, command, args)

    def _handlePrivMsg(self, msg):
        senderNick = msg.prefix
        senderIdent = msg.prefix

        if msg.prefix.find("!") != -1:  # nicknames can change, indent is harder to change
            senderNick, senderIdent = msg.prefix.split("!", 1)

        targets = msg.args[:-1]
        message = msg.args[-1].strip().lower()

        # TODO: do not just hardcode it. Store it in a config file.
        if self.CHANNEL in targets:
            if message.startswith("hello"):
               self._sendMessage("PRIVMSG %s :Hello... Is it me you're looking for?" % self.CHANNEL)
            if message.startswith("i can see it in your eyes"):
               self._sendMessage("PRIVMSG %s :I can see it in your smile" % self.CHANNEL)
            if message.startswith("you're all i've ever wanted"):
               self._sendMessage("PRIVMSG %s :...and my arms are open wide!" % self.CHANNEL)
               self._sendMessage("PRIVMSG %s :'Cause you know just what to say" % self.CHANNEL)
               self._sendMessage("PRIVMSG %s :And you know just what to do" % self.CHANNEL)
               self._sendMessage("PRIVMSG %s :And I want to tell you so much..." % self.CHANNEL)
               self._sendMessage("PRIVMSG %s :...I love you!" % self.CHANNEL)
        elif self.NICK in targets:
            if message.startswith("help"):
                for line in HELP_MSG:
                    self._sendMessage("PRIVMSG %s :%s" % (senderNick, line))

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

