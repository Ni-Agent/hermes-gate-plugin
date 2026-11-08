"""Hermes gateway lifecycle owner for Gate's independent task runtime."""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import pathlib
import tempfile
import threading

from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult

log = logging.getLogger("hermes.gate")


class GateAdapter(BasePlatformAdapter):
    def __init__(self, config, runtime_factory, directory):
        super().__init__(config, Platform("gate"))
        self._runtime_factory = runtime_factory
        self._directory = pathlib.Path(directory)
        self._runtime = None
        self._thread = None
        self._stopping = threading.Event()
        self._lifecycle = asyncio.Lock()
        self._loop = None
        self._generation = 0
        self._cleanup_task = None

    @property
    def send_path_degraded(self):
        return self._runtime is None or not self._runtime.connected

    def _status(self, state, error=None):
        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(prefix=".listener-", dir=self._directory)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"state": state, "error": error}, f)
            os.replace(name, self._directory / "listener.json")
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _connection_changed(self, generation, connected, error):
        if generation != self._generation or self._stopping.is_set():
            return
        self._status("connected" if connected else "reconnecting", error)
        self._mark_connected()  # Publishes degraded state while SSE is reconnecting.

    def _failed(self, generation, error):
        if generation != self._generation or self._stopping.is_set():
            return
        self._status("failed", type(error).__name__)
        self._set_fatal_error(
            "gate_listener_failed",
            "Gate task pickup could not start.",
            retryable=not isinstance(error, (ValueError, RuntimeError)),
        )

    async def connect(self, *, is_reconnect=False):
        async with self._lifecycle:
            if self._thread and self._thread.is_alive():
                return self.is_connected and not self._stopping.is_set()
            self._loop = asyncio.get_running_loop()
            self._generation += 1
            generation = self._generation
            self._stopping = threading.Event()
            stopping = self._stopping
            self._runtime = None
            self._status("connecting")
            context = contextvars.copy_context()

            def report(connected, error):
                if not self._loop.is_closed():
                    self._loop.call_soon_threadsafe(
                        self._connection_changed, generation, connected, error
                    )

            def run():
                runtime = None
                try:
                    runtime = self._runtime_factory(report)
                    self._runtime = runtime
                    if stopping.is_set():
                        runtime.request_stop()
                    else:
                        runtime.listen()
                except Exception as error:
                    log.warning("Gate task pickup stopped: %s", type(error).__name__)
                    if not self._loop.is_closed():
                        self._loop.call_soon_threadsafe(self._failed, generation, error)
                finally:
                    if runtime is not None:
                        runtime.stop()

            self._thread = threading.Thread(
                target=context.run,
                args=(run,),
                name="Gate gateway listener",
                daemon=True,
            )
            self._thread.start()
            self._mark_connected()
            return True

    def request_stop(self):
        self._stopping.set()
        if self._runtime is not None:
            self._runtime.request_stop()

    async def disconnect(self):
        async with self._lifecycle:
            self.request_stop()
            if self._thread:
                await asyncio.to_thread(self._thread.join, 4)
                if self._thread.is_alive():
                    self._status("stopping")
                    raise RuntimeError("Gate task worker is still stopping")
            self._status("stopped")
            self._mark_disconnected()

    def close_from_plugin(self):
        self.request_stop()
        if self._loop is not None and not self._loop.is_closed():

            def close():
                if self._cleanup_task is None or self._cleanup_task.done():
                    self._cleanup_task = asyncio.create_task(self.disconnect())
                    self._cleanup_task.add_done_callback(self._cleanup_finished)

            self._loop.call_soon_threadsafe(close)

    @staticmethod
    def _cleanup_finished(task):
        if not task.cancelled() and task.exception():
            log.warning(
                "Gate shutdown needs attention: %s", type(task.exception()).__name__
            )

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=False, error="Gate has no chat destinations.")

    async def get_chat_info(self, chat_id):
        return {"name": "Gate", "type": "service"}
