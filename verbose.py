import logging


LOG_LEVEL = logging.DEBUG


class Verbose(object):
    """ Inherit this class to call self._print and get line number etc."""
    def __init__(self, name=None):
        self._name = name if name else self.__class__.__name__
        self._init_logging()

    def _init_logging(self):
        self.logger = logging.getLogger(self._name)
        self.logger.setLevel(level=LOG_LEVEL)
