"""Simulated System V Inter-Process Communication (IPC) Message Queue subsystem."""

import itertools
import threading
import time
from typing import Dict, List, Optional, Tuple, Any

IPC_PRIVATE = 0
IPC_CREAT = 512  # 0o1000
IPC_EXCL = 1024  # 0o2000


def get_current_pid() -> int:
    """Resolve the simulated PID of the calling thread.

    If the current thread is not spawned by the Scheduler, returns 0 (system/shell).
    """
    name = threading.current_thread().name
    if name.startswith("process-"):
        try:
            return int(name.split("-")[1])
        except (ValueError, IndexError):
            pass
    return 0


class Message:
    """Represents a single message stored in a message queue."""

    def __init__(self, msg_type: int, text: str, sender_pid: int):
        self.msg_type = msg_type
        self.text = text
        self.sender_pid = sender_pid
        self.timestamp = time.time()


class MessageQueue:
    """Thread-safe simulated System V message queue with capacity limits."""

    def __init__(self, msqid: int, key: int, creator_pid: int, max_bytes: int = 16384):
        self.msqid = msqid
        self.key = key
        self.creator_pid = creator_pid
        self.messages: List[Message] = []
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.max_bytes = max_bytes
        self.removed = False

        # Statistics
        self.last_snd_pid = 0
        self.last_rcv_pid = 0
        self.last_snd_time = 0.0
        self.last_rcv_time = 0.0

    def send(
        self, msg_type: int, text: str, sender_pid: int, block: bool = True
    ) -> bool:
        """Send a message of msg_type to the queue. Blocks if the queue is full."""
        if not isinstance(msg_type, int):
            raise TypeError("Message type must be an integer")
        if msg_type <= 0:
            raise ValueError("Message type must be a positive integer (> 0)")
        if not isinstance(text, str):
            raise TypeError("Message text must be a string")

        with self.lock:
            while True:
                if self.removed:
                    raise OSError("Message queue was removed.")

                # Calculate currently used bytes
                current_bytes = sum(len(msg.text) for msg in self.messages)
                if current_bytes + len(text) <= self.max_bytes:
                    break

                if not block:
                    raise BlockingIOError("Message queue is full.")

                self.condition.wait()

            msg = Message(msg_type, text, sender_pid)
            self.messages.append(msg)
            self.last_snd_pid = sender_pid
            self.last_snd_time = msg.timestamp
            self.condition.notify_all()
            return True

    def receive(
        self, msg_type: int = 0, block: bool = True, timeout: Optional[float] = None
    ) -> Optional[Message]:
        """Receive a message from the queue.

        msg_type:
            0: receive first message on the queue (FIFO).
            >0: receive first message of type msg_type.
            <0: receive first message of lowest type <= abs(msg_type).
        """
        if not isinstance(msg_type, int):
            raise TypeError("Message type must be an integer")

        with self.lock:

            def find_msg():
                for idx, msg in enumerate(self.messages):
                    if msg_type == 0:
                        return idx, msg
                    elif msg_type > 0:
                        if msg.msg_type == msg_type:
                            return idx, msg
                    else:  # msg_type < 0
                        limit = abs(msg_type)
                        matching = [
                            (i, m)
                            for i, m in enumerate(self.messages)
                            if m.msg_type <= limit
                        ]
                        if matching:
                            # Pick the matching message with the lowest msg_type
                            lowest_idx, lowest_msg = min(
                                matching, key=lambda item: item[1].msg_type
                            )
                            return lowest_idx, lowest_msg
                return -1, None

            if block:
                start_time = time.time()
                while True:
                    if self.removed:
                        raise OSError("Message queue was removed.")

                    idx, msg = find_msg()
                    if msg is not None:
                        self.messages.pop(idx)
                        self.last_rcv_pid = get_current_pid()
                        self.last_rcv_time = time.time()
                        self.condition.notify_all()  # Wake up blocked senders
                        return msg
                    if timeout is not None:
                        elapsed = time.time() - start_time
                        remaining = timeout - elapsed
                        if remaining <= 0:
                            return None
                        self.condition.wait(remaining)
                    else:
                        self.condition.wait()
            else:
                if self.removed:
                    raise OSError("Message queue was removed.")
                idx, msg = find_msg()
                if msg is not None:
                    self.messages.pop(idx)
                    self.last_rcv_pid = get_current_pid()
                    self.last_rcv_time = time.time()
                    self.condition.notify_all()  # Wake up blocked senders
                    return msg
                return None


class IPCManager:
    """Manager for simulated IPC facilities registered on the Kernel."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.queues: Dict[int, MessageQueue] = {}
        self.key_to_id: Dict[int, int] = {}
        self._id_iter = itertools.count(1)
        self._lock = threading.Lock()

    def msgget(self, key: int, msgflg: int = 0) -> int:
        """Get or create a message queue ID."""
        if not isinstance(key, int):
            raise TypeError("Queue key must be an integer")
        if not isinstance(msgflg, int):
            raise TypeError("Message flags must be an integer")

        current_pid = get_current_pid()
        with self._lock:
            if key == IPC_PRIVATE:
                msqid = next(self._id_iter)
                self.queues[msqid] = MessageQueue(msqid, key, current_pid)
                return msqid

            if key in self.key_to_id:
                msqid = self.key_to_id[key]
                if (msgflg & IPC_CREAT) and (msgflg & IPC_EXCL):
                    raise FileExistsError(
                        f"Message queue with key {key} already exists."
                    )
                return msqid
            else:
                if msgflg & IPC_CREAT:
                    msqid = next(self._id_iter)
                    self.queues[msqid] = MessageQueue(msqid, key, current_pid)
                    self.key_to_id[key] = msqid
                    return msqid
                else:
                    raise FileNotFoundError(f"No message queue with key {key} found.")

    def msgsnd(self, msqid: int, msg_type: int, text: str, block: bool = True) -> bool:
        """Send a message to a queue ID."""
        with self._lock:
            queue = self.queues.get(msqid)
        if not queue:
            raise KeyError(f"Invalid message queue ID: {msqid}")
        current_pid = get_current_pid()
        return queue.send(msg_type, text, current_pid, block=block)

    def msgrcv(
        self,
        msqid: int,
        msg_type: int = 0,
        block: bool = True,
        timeout: Optional[float] = None,
    ) -> Optional[Tuple[int, str, int, float]]:
        """Receive a message from a queue ID."""
        with self._lock:
            queue = self.queues.get(msqid)
        if not queue:
            raise KeyError(f"Invalid message queue ID: {msqid}")
        msg = queue.receive(msg_type, block=block, timeout=timeout)
        if msg:
            return (msg.msg_type, msg.text, msg.sender_pid, msg.timestamp)
        return None

    def msgctl(self, msqid: int, cmd: str) -> Any:
        """Control message queue behavior (e.g. remove queue or query status)."""
        with self._lock:
            queue = self.queues.get(msqid)

        if not queue:
            raise KeyError(f"Invalid message queue ID: {msqid}")

        if cmd == "IPC_RMID":
            with self._lock:
                self.queues.pop(msqid, None)
                if queue.key != IPC_PRIVATE:
                    self.key_to_id.pop(queue.key, None)
            with queue.lock:
                queue.removed = True
                queue.condition.notify_all()
            return True
        elif cmd == "IPC_STAT":
            with queue.lock:
                return {
                    "msqid": queue.msqid,
                    "key": queue.key,
                    "creator_pid": queue.creator_pid,
                    "msg_qnum": len(queue.messages),
                    "msg_bytes": sum(len(msg.text) for msg in queue.messages),
                    "msg_qbytes": queue.max_bytes,
                    "last_snd_pid": queue.last_snd_pid,
                    "last_rcv_pid": queue.last_rcv_pid,
                    "last_snd_time": queue.last_snd_time,
                    "last_rcv_time": queue.last_rcv_time,
                }
        else:
            raise ValueError(f"Unknown msgctl command: {cmd}")
