#!/usr/bin/env python3
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
import time
import threading
import argparse

from message import Message
import teamerconfig as cfg

TRACE_LVL = 5
logging.addLevelName(TRACE_LVL, "TRACE")
def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE_LVL):
        self._log(TRACE_LVL, message, args, **kwargs)
logging.Logger.trace = trace

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
    BURST_TIMEOUT = 10
    BURST_MSG_NO = 5
    MSG_INTERVAL = 0.8

    def __init__(self):
        self._s = socket.socket()
        self._s.settimeout(cfg.timeout)
        self._connected = False
        self._onChannel = False

        self._lastMessageTime = int(time.time()) - self.BURST_TIMEOUT  # with a precision in seconds
        self._queue = []
        self._queueReaderThread = threading.Thread(target = self._queueHandler)
        self._queueWriteLock = threading.Condition()
        self._stopQueueReaderThread = threading.Event()

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
            self._finishWork()

    def joinChannel(self):
        if self._connected is True:
            self._sendMessage("JOIN %s" % cfg.channel, True)

    def run(self):
        self.joinChannel()
        self._s.settimeout(None) # no timeout, blocking mode

        self._queueReaderThread.start()

        while self._connected is True:
            msgs = self._receiveMessages()
            for msg in msgs:
                if msg is None:
                    continue

                if msg.command == "PING":
                    self._sendMessage("PONG")
                elif msg.command == "KILL":
                    log.info("Disconnected from a server")
                    self._finishWork()
                    break # TODO: maybe try to reconnect?
                elif msg.command == "JOIN" and msg.prefix.startswith(cfg.nick):
                    log.debug("Joined %s" % msg.args[0])
                    self._onChannel = True
                elif msg.command == "KICK" and msg.args[0] == cfg.channel and msg.args[1] == cfg.nick:
                    log.debug("Kicked from %s" % msg.args[0])
                    self._onChannel = False
                    self.joinChannel()
                else:
                    try:
                        if self._onChannel:
                            resps = cfg.messageHandler(msg, log)
                            self._handleOutgoingMessages(resps)
                    except Exception as e:
                        log.debug("Exception occured during custom message handling:")
                        log.debug("  %s" % e)

    def _handleOutgoingMessages(self, resps):
        if resps is None:
            return

        # send anything other than PRIVMSG immediately
        for i, resp in enumerate(resps):
            if resp.command != "PRIVMSG":
                self._sendMessage(self._serializeMessage(resp))
                del resps[i]

        with self._queueWriteLock:
            self._queue.extend(resps)
            self._queueWriteLock.notifyAll()

    def _queueHandler(self):
        """Should be called in the other thread"""
        while not self._stopQueueReaderThread.isSet():
            with self._queueWriteLock:
                # blocks until is notified.
                # wait (release lock) until there's something to be sent
                while len(self._queue) == 0:
                    if self._stopQueueReaderThread.isSet():
                        return
                    self._queueWriteLock.wait()

                now = time.time()
                if (now - self._lastMessageTime) >= self.BURST_TIMEOUT:
                    # burst maximum last 5 messages when the last message was sent a long ago
                    for msg in self._queue[:self.BURST_MSG_NO]:
                        self._sendMessage(self._serializeMessage(msg))
                    self._queue = self._queue[self.BURST_MSG_NO:]
                else:
                    msg = self._queue.pop(0)
                    self._sendMessage(self._serializeMessage(msg))
                self._lastMessageTime = now
            time.sleep(self.MSG_INTERVAL)

    def _finishWork(self):
        self._connected = False
        self._onChannel = False
        self._stopQueueReaderThread.set()
        with self._queueWriteLock:
            self._queue = []
            self._queueWriteLock.notifyAll()
        self._queueReaderThread.join()

    def _startConnection(self):
        try:
            self._s.connect((cfg.host, cfg.port))
        except socket.timeout as e:
            log.error("Timeout on connection to %s:%s" % (cfg.host, cfg.port))
            raise ExitWithStatus(Status.CONNECTION_FAILURE)
        except socket.gaierror as e:
            log.error("Cannot resolve a hostname: %s"  % cfg.host)
            log.error(e.string)
            raise ExitWithStatus(Status.CONNECTION_FAILURE)

    def _sendMessage(self, msg, critical = False):
        try:
            s = "%s\r\n" % msg
            log.trace(">> %s" % s)
            self._s.send(s.encode())
        except socket.timeout as e:
            log.error("Message timeout!")
            log.debug("  %s" % msg)
            if critical is True:
                log.error("It was a critical message! Terminating!")
                raise ExitWithStatus(Status.MESSAGE_TIMEOUT)

    def _receiveMessages(self, bufsize = 4096):
        buf = ""
        while not buf.endswith("\r\n"):
            buf = buf + self._s.recv(bufsize).decode()
        log.trace(buf)
        lines = buf.split("\r\n")
        return [self._parseMessage(line) for line in lines]

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

def prepareOptions():
    parser = argparse.ArgumentParser(description = "IRC Bot")
    parser.add_argument("--dlevel", metavar = "LVL", dest = "loggingLevel", type = str,
        default = "info", choices = ["info", "debug", "trace"],
        help = "sets the logging level: trace|debug|info")

    return parser

def setLoggingLevel(lvl):
    lvl = lvl.lower()
    if lvl == "info":
        log.setLevel(logging.INFO)
    elif lvl == "debug":
        log.setLevel(logging.DEBUG)
    elif lvl == "trace":
        log.setLevel(TRACE_LVL)
    else:
        log.error("Unknown debug level: %s" % lvl)
        log.setLevel(logging.INFO)

def main():
    optParser = prepareOptions()
    args = optParser.parse_args()

    setLoggingLevel(args.loggingLevel)
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

