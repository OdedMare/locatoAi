class FlunksRunner:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def run(self):
        raise NotImplementedError
