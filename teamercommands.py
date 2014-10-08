#-*- coding: utf-8 -*-

import textwrap
from random import shuffle

def nextToken(message):
    token = message
    trailing = ""
    if " " in message:
        token, trailing = message.split(" ", 1)
        token = token.lower()
    return token, trailing


class BotCommand:
    """Base Bot Command"""
    def __init__(self, cmd, priv, publ):
        self._command = cmd
        self._isPrivate = priv
        self._isPublic = publ

        self._helpLines = textwrap.dedent(self.__doc__)

    @property
    def command(self):
        return self._command

    @property
    def private(self):
        return self._isPrivate

    @property
    def public(self):
        return self._isPublic


    def helpReply(self, receiver):
        if self._helpLines != "":
            return self._helpLines
        return None
    def parseMessage(self, sender, receiver, args):
        """Interface method. Will be called when message meets requirements.
        Note however that it will NOT receive a full message, only its arguments.
        The following variables will be resolved:
          %(sendernick)s, %(botname)s, %(botnick)s
        """
        pass

    def _isreceiverPrivate(self, receiver):
        return not receiver.startswith("#") # lol

    def _returnMessageToPrivate(self, message, receiver):
        if self._isreceiverPrivate(receiver):
            return message
        return None

    def hash(self):
        return hash(self.command)

    def __eq__(self, other):
        return self.command == other.command

class HelpCommand(BotCommand):
    """\
    \02***** %(botname)s Help *****\02
    For more information about command, type:
    \02/msg %(botnick)s help <command>

    Available commands:
    \02LIST SHUFFLE\02

    License: GPL3 or any later
    Source code and wiki: https://github.com/mgoral/teamer-bot
    ***** End of Help *****"""

    def __init__(self):
        super().__init__("help", priv = True, publ = False)

    def parseMessage(self, sender, receiver, args):
        args = args.split()
        if len(args) > 0:
            cmd = commands.get(args[0])
            if cmd is not None:
                return cmd.helpReply(receiver)
            return "No help for command: \02%s\02" % args[0]
        return self.helpReply(receiver)


class ListCommand(BotCommand):
    """\
    \02LIST\02: manages the user-shared list of items.
    SYNTAX:
      list new|rm|len <listname>
      list show <listname> [<from>:<to>]
      list push <listname> [<item>][,<item>]...
      list pop <listname> [<itemNumber>]
      list"""

    def __init__(self, sizelimit):
        super().__init__("list", priv = True, publ = True)
        self._sizelimit = sizelimit
        self._lists = {
            # name : itemList
        }

    def parseMessage(self, sender, receiver, args):
        if args == "":
            # print available list names
            if len(self._lists) > 0:
                l = list(self._lists.keys())
                l.sort()
                return "; ".join(l)
            return None

        subcommand, args = nextToken(args)
        listname, args = nextToken(args)
        subcommand = subcommand.lower()

        if subcommand == "new":
            return self._new(listname, receiver)
        elif subcommand == "rm":
            return self._rm(listname, receiver)
        elif subcommand == "len":
            return self._len(listname, receiver)
        elif subcommand == "show":
            return self._show(listname, args, receiver)
        elif subcommand == "push":
            return self._push(listname, args, receiver)
        elif subcommand == "pop":
            return self._pop(listname, args, receiver)
        else:
            return self._returnMessageToPrivate("Unknown subcommand: '%s'" % subcommand, receiver)

    def _new(self, listname, rec):
        if listname in self._lists:
            return self._returnMessageToPrivate("List '%s' exists!" % listname, rec)
        else:
            self._lists[listname] = []

    def _rm(self, listname, rec):
        if listname in self._lists:
            del self._lists[listname]
        else:
            return self._returnMessageToPrivate("List '%s' doesn't exist" % listname, rec)

    def _len(self, listname, rec):
        try:
            return str(len(self._lists[listname]))
        except KeyError:
            return self._returnMessageToPrivate("List '%s' doesn't exist" % listname, rec)

    def _show(self, listname, args, rec):
        toShow = self._lists.get(listname)
        if toShow is None:
            return

        if len(toShow) == 0:
            return "<empty list>"

        listFrom, listTo = (0, len(toShow))

        listGrep, args = nextToken(args)
        try:
            if listGrep != "" and ":" in listGrep:
                f, t = listGrep.split(":", 1)
                listFrom = int(f)
                listTo = int(t)
        except:
            return self._returnMessageToPrivate("Incorrect sublist format", rec)

        if listFrom < 0:
            listFrom = len(toShow) + listFrom
        ret = ["%d: %s" % (listFrom + no, item) for no, item in enumerate(toShow[listFrom:listTo])]
        return "\n".join(ret)

    def _push(self, listname, args, rec):
        try:
            if (self._sizelimit > 0 and len(self._lists[listname]) >= self._sizelimit):
                return "'%s' reached its maximum size: %d" % (listname, self._sizelimit)
            self._lists[listname].extend(args.split(","))
        except:
            return self._returnMessageToPrivate("Push failed", rec)

    def _pop(self, listname, args, rec):
        no = 0
        if args != "":
            try:
                reqNo, _ = nextToken(args)
                no = int(reqNo)
            except:
                return self._returnMessageToPrivate("Incorrect number: %s" % reqNo, rec)

        try:
            ret = self._lists[listname].pop(no)
            return ret
        except KeyError:
            return self._returnMessageToPrivate("Pop failed: no list '%s'" % listname, rec)
        except:
            return self._returnMessageToPrivate("Pop failed", rec)

class ShuffleCommand(BotCommand):
    """\
    \02SHUFFLE\02: prints randomly shuffled list.
    SYNTAX:
      shuffle <item>[,<item>]..."""

    def __init__(self):
        super().__init__("shuffle", priv = True, publ = True)

    def parseMessage(self, sender, receiver, args):
        toShuffle = args.split(",")
        shuffle(toShuffle)
        return ",".join(toShuffle)

commands = {
    "help" : HelpCommand(),
    "list" : ListCommand(15),
    "shuffle" : ShuffleCommand(),
}
