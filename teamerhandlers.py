#-*- coding: utf-8 -*-

from message import Message
import teamercommands as cmds
import teamerconfig as cfg

def makeMessage(cmd, args = [], prefix = ""):
    return Message(prefix, cmd, args)

def makePrivMsg(receipent, text):
    if text == "":
        text = " "
    return makeMessage("PRIVMSG", args = [receipent, text])

def parseCommand(sender, receipent, message):
    isPrivate = receipent is not cfg.channel
    isPublic = not isPrivate

    helpNeeded = False

    token, message = cmds.nextToken(message)

    command = cmds.commands.get(token.lower())
    if command is None:
        if isPrivate is True:
            return "Unknown command: \02%s\02" % token
        return None

    if (isPrivate is command.private ) or (isPublic is command.public):
        return command.parseMessage(sender, receipent, message)

    return None

def handlePrivMsg(msg):
    fullSender = msg.prefix
    senderNick = msg.prefix
    senderIdent = msg.prefix

    if "!" in msg.prefix:  # nicknames can change, indent is harder to change
        senderNick, senderIdent = msg.prefix.split("!", 1)

    targets = msg.args[:-1]
    message = msg.args[-1].strip()

    respondTo = None

    if cfg.channel in targets:
        respondTo = cfg.channel
        # on public channels messages to bot MUST start with an exclamation mark
        if not message.startswith("!"):
            return None
        else:
            message = message[1:]
    elif cfg.nick in targets:
        respondTo = senderNick
    else:
        return None

    taunt = parseCommand(fullSender, respondTo, message)

    # create messages from returned string
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
