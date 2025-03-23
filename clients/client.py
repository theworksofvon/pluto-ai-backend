import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from logger import logger

Listener = Callable[..., Any]
Listeners = Dict[str | Enum, List[Listener]]


class StrEnum(str, Enum):
    pass


class Client(ABC):
    name = "Client"
    _listeners: Listeners
    _max_retries = 5
    _time_interval = 10

    class Events(StrEnum):
        DISCONNECTED = "Disconnected"
        WAIT = "Wait"
        CONNECTING = "Connecting"
        RETRYING = "Retrying"
        CONNECTED = "Connected"
        RECONNECTED = "Reconnected"
        READY = "Ready"
        STALE = "Stale"
        END = "End"
        CLOSED = "Close"
        PONG = "Pong"
        ERROR = "Error"

    def __init__(self):
        self._listeners = {}
        self._is_running = False

    async def init(self, *args, **kwargs):
        await self.connect(*args, **kwargs)
        asyncio.create_task(self.monitor(self._time_interval))

    @abstractmethod
    async def _connect(self, *args, **kwargs) -> Any:
        """
        Abstract method to establish a connection. Must be implemented by subclasses.

        Returns:
            Any: The result of the connection process. Typically, the engine/connection.
        """
        raise NotImplementedError()

    @abstractmethod
    async def _close(self) -> Any:
        """
        Abstract method to close the connection. Must be implemented by subclasses.

        Returns:
            Any: The result of the close operation.
        """
        raise NotImplementedError()

    @abstractmethod
    async def _monitor(self):
        """
        Abstract method to monitor the connection health. Must be implemented by subclasses.
        """
        raise NotImplementedError()

    async def close(self) -> Any:
        self.emit(self.Events.WAIT)
        logger.info(f"{self.name}: Closing Connection")
        logger.info(f"{self.name}: Stopping Monitor if enabled")
        self._is_running = False
        try:
            await self._close()
            logger.info(f"{self.name}: Connection Closed")
            self.emit(self.Events.CLOSED)
        except Exception as e:
            logger.info(f"{self.name}: Error Closing Connection: {str(e)}")
            self.emit(self.Events.ERROR, str(e))

    async def monitor(self, time_interval: float):
        logger.info(f"{self.name}: Monitor Started")
        while self._is_running:
            try:
                await self._monitor()
                self.emit(self.Events.PONG)
            except Exception as e:
                self.emit(self.Events.STALE, str(e))
                logger.info(f"{self.name}: Monitor Probe Failed {str(e)}")
            await asyncio.sleep(time_interval)
        logger.info(f"{self.name}: Monitor Stopped")

    async def connect(self, *args: Any, **kwargs: Any):
        """
        Connects to the client using the provided arguments. Implements retry logic.
        Returns:
            The result of the connection process. Typically, the engine/connection.
        """
        retry_count = 0
        while retry_count <= self._max_retries:
            try:
                logger.info(f"{self.name}: Connecting")
                self.emit(self.Events.CONNECTING)
                result = await self._connect(*args, **kwargs)
                self.emit(self.Events.CONNECTED)
                self._is_running = True
                # One time check
                await self._monitor()
                self.emit(self.Events.READY)
                logger.info(f"{self.name}: Connected")
                return result
            except Exception as e:
                retry_count += 1
                if retry_count > self._max_retries:
                    logger.info(f"{self.name}: Max retry attempts reached. Last error: {e}")
                    self.emit(self.Events.END, str(e))
                    raise
                else:
                    retry_delay = retry_count * 0.1
                    logger.info(
                        f"{self.name}: Failed to connect with Error (Will Retry): {e}"
                    )
                    self.emit(self.Events.RETRYING, str(e))
                    await asyncio.sleep(retry_delay)

    def emit(self, event: StrEnum, *args: Any, **kwargs: Any):
        if event in self._listeners:
            for fn in self._listeners[event]:
                fn(*args, **kwargs)

    def on(self, event: StrEnum, fn: Optional[Listener] = None):
        if fn:
            return self._on(event, fn)
        return self._decorated_on(event)

    def _on(self, event: StrEnum, fn: Listener):
        if event in self._listeners:
            self._listeners[event].append(fn)
        else:
            self._listeners[event] = [fn]

    def _decorated_on(self, event: StrEnum):
        def on_decorator(fn: Listener):
            self._on(event, fn)
            return fn

        return on_decorator
