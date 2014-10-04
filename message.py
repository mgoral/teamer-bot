class Message:
    """Merely a wrapper for 3 named fields."""
    def __init__(self, prefix = "", command = "", args = []):
        self.prefix = prefix
        self.command = command
        self.args = args
