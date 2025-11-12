class ReverbWrongSideError(Exception):
    def __init__(self, side):
        super().__init__(f"Wrong side: '{side}' side.")


class ReverbUIDAlreadyInitError(Exception):
    def __init__(self, ro, uid):
        super().__init__(
            f"The ReverbObject '{ro.__class__.__name__}' is already init with {uid=} already taken! Only new ReverbObject can have a new uid!")


class ReverbUIDUnknownError(Exception):
    def __init__(self):
        super().__init__(f"The uid is 'Unknown'! This should'nt be 'Unknown'!")


class ReverbObjectAlreadyExistError(Exception):
    def __init__(self, ro):
        super().__init__(f"The ReverbObject '{ro.__class__.__name__}' is already into the ReverbManager!")


class ReverbObjectNotFoundError(Exception):
    def __init__(self, uid):
        super().__init__(f"ReverbObject not found with {uid=}")


class ReverbTypeNotFoundError(Exception):
    def __init__(self, t):
        super().__init__(f"The type={t} is not found into the registry!")
