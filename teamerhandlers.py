from message import Message
import teamerconfig as cfg

# Note spaces on "empty" lines...
HELP_MSG = """\02***** %(botname)s Help *****\02
For more information about command, type:
\02/msg %(botnick)s help <command>
 
Available commands:
\02SET TAUNT UNSET VARCLEAR VARLIST\02
***** End of Help *****"""

# usable variables for taunts:
# %(sendernick)s
# %(botname)s, %(botnick)s
channelTaunts = {
    "hello" : "Hello, %(sendernick)s",
    "szama" : "Message is incorrecto...",
}

variables = {}

privateTaunts = {
    "help" : HELP_MSG,
}

def makeMessage(cmd, args = [], prefix = ""):
    return Message(prefix, cmd, args)

def makePrivMsg(receipent, text):
    return makeMessage("PRIVMSG", args = [receipent, text])

def nextToken(message):
    token = message
    trailing = ""
    if " " in message:
        token, trailing = message.split(" ", 1)
        token = token.lower()
    return token, trailing

def parseCommand(message, defaultReply = None):
    helpNeeded = False
    token, message = nextToken(message)
    if token == "help":
        helpNeeded = True
        token, message = nextToken(message)

    if token == "set":
        if helpNeeded:
            return "set <variable> <message>\nStores a message under a variable."
        key, value = nextToken(message)
        if key != "" and value != "":
            variables[key] = value
            return "Done"
        return "Failed. Required fields: <variable> <message>."
    elif token == "unset":
        if helpNeeded:
            return "unset <variable>\nRemoves message stored under a variable."
        del variables[message]
        return "Done"
    elif token == "taunt":
        if helpNeeded:
            return "taunt <variable>\nPrints a message associated to a variable."
        value = variables.get(message)
        if value is not None:
            return value
        return None
    elif token == "varlist":
        if helpNeeded:
            return "Returns a list of stored variables."
        return " ".join(variables.keys())
    elif token == "varclear":
        if helpNeeded:
            return "Clears all stored variables."
        variables.clear()
        return "Done"
    return defaultReply

def handlePrivMsg(msg):
    senderNick = msg.prefix
    senderIdent = msg.prefix

    if "!" in msg.prefix:  # nicknames can change, indent is harder to change
        senderNick, senderIdent = msg.prefix.split("!", 1)

    targets = msg.args[:-1]

    message = msg.args[-1].strip()
    messageL = message.lower() # ugly hack...

    taunt = None
    respondTo = None

    if cfg.channel in targets:
        respondTo = cfg.channel
        taunt = None
        if messageL.startswith("taunt"):
            taunt = parseCommand(message)
        if taunt is None:
            taunt = channelTaunts.get(messageL)
    elif cfg.nick in targets:
        respondTo = senderNick
        taunt = parseCommand(message)
        if taunt is None: # it's not a real command, try to say something
            taunt = privateTaunts.get(messageL)
        if taunt is None: # fallback to public messages
            taunt = channelTaunts.get(messageL)
        if taunt is None:
            taunt = "Invalid command. Use \02/msg %(botnick)s help\02 for help."

    if taunt is not None:
        tauntList = taunt.split("\n")
        ret = []
        for line in tauntList:
            line = line % {"sendernick" : senderNick, "botnick" : cfg.nick, "botname" : cfg.realname }
            ret.append(makePrivMsg(respondTo, line))
        return ret
    return None

def handleMessage(msg, log):
    if msg.command == "PRIVMSG":
        return handlePrivMsg(msg)
    return None
