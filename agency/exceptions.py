## TODO: more specific llms errors


class CommunicationsProtocolError(Exception):
    msg: str
    status_code: int

    def __init__(self, msg: str, status_code: int):
        super().__init__(msg)
        self.msg = msg
        self.status_code = status_code
