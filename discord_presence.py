"""Estado opcional del launcher en la aplicación de escritorio de Discord."""

import threading
import time

from pypresence import Presence


class DiscordPresence:
    def __init__(self, application_id: str):
        self.application_id = application_id.strip()
        self._stop = threading.Event()
        self._thread = None

    def start(self) -> None:
        if self.application_id.isdecimal():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        started = int(time.time())
        while not self._stop.is_set():
            rpc = None
            try:
                rpc = Presence(self.application_id)
                rpc.connect()
                while not self._stop.is_set():
                    rpc.update(details="En Planeta Panetones Launcher", state="Preparando Minecraft", start=started)
                    self._stop.wait(30)
            except Exception:
                self._stop.wait(30)
            finally:
                if rpc is not None:
                    try:
                        rpc.close()
                    except Exception:
                        pass
