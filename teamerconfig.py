# This is a simple configuration file for teamer bot
# It will be imported by it directly

import teamerhandlers as handlers

# password for a connection. Bot will send it when establishing a connection to a server.
# Might be None. In that case PASS command will not be sent.
password = None

# server address and port
host = "chat.freenode.net"
port = 6667

# name of the channel that bot will connect to
channel = "#bbconf"

# Bot information
ident = "bbconf-teamer"
nick = "teamer"
realname = "BBConf Teamer Bot"
owner = "virgoerns"

# timeout for establishing initial connection to server. When bot joins a channel it's not used
# anymore
timeout = 30.0

# callable message handler (here fun begins ;)). It should have the following signature:
#
# def handler(msg, log)
#    return [Message("prefix", "command", ["arg1", "arg2", "trailing banana"])]

# msg: structure containing the following fields:
#    prefix  (string), 
#    command (string)
#    args    (list of strings).
#
# log: instance of a logger. For details see Python module `logging`
#
# return: list of strings containing a valid IRC message (@see RFC 1459) or None if there is no
#         response. List might be also empty in that case.
messageHandler = handlers.handleMessage
