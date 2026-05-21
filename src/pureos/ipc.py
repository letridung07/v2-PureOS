"""Simulated System V Inter-Process Communication (IPC) Message Queue subsystem."""

from __future__ import annotations

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


class SharedMemorySegment:
    """Simulated System V shared memory segment."""

    def __init__(self, shmid: int, key: int, creator_pid: int, size: int):
        self.shmid = shmid
        self.key = key
        self.creator_pid = creator_pid
        self.size = size
        self.buf = bytearray(size)
        self.nattch = 0
        self.lock = threading.RLock()
        self.removed = False
        self.buffers: List[SharedMemoryBuffer] = []

        # Statistics
        self.last_attach_time = 0.0
        self.last_detach_time = 0.0
        self.last_attach_pid = 0
        self.last_detach_pid = 0

    def attach(self, pid: int, manager) -> SharedMemoryBuffer:
        with self.lock:
            if self.removed and self.nattch == 0:
                raise OSError("Shared memory segment has been destroyed.")
            self.nattch += 1
            self.last_attach_time = time.time()
            self.last_attach_pid = pid
            buf = SharedMemoryBuffer(self, manager, pid)
            self.buffers.append(buf)
            return buf

    def detach(self, pid: int) -> bool:
        with self.lock:
            if self.nattch <= 0:
                return False
            self.nattch -= 1
            self.last_detach_time = time.time()
            self.last_detach_pid = pid

            # Detach any buffers associated with this PID
            detached_any = False
            remaining_buffers = []
            for buf in self.buffers:
                if buf._pid == pid:
                    buf._detached = True
                    detached_any = True
                else:
                    remaining_buffers.append(buf)
            self.buffers = remaining_buffers

            # If no buffer matched this pid directly, detach the first one as fallback
            if not detached_any and self.buffers:
                buf = self.buffers.pop(0)
                buf._detached = True
                detached_any = True

            return True


class SharedMemoryBuffer:
    """A thread-safe proxy wrapper around a shared bytearray.

    Validates that the underlying segment has not been destroyed.
    """

    def __init__(self, segment: SharedMemorySegment, manager, pid: int):
        self._segment = segment
        self._manager = manager
        self._pid = pid
        self._detached = False

    def _validate(self):
        if self._detached:
            raise OSError("Shared memory buffer has been detached.")
        if self._segment.removed and self._segment.nattch == 0:
            raise OSError("Shared memory segment has been destroyed.")

    def __getitem__(self, key):
        with self._segment.lock:
            self._validate()
            return self._segment.buf[key]

    def __setitem__(self, key, value):
        with self._segment.lock:
            self._validate()
            self._segment.buf[key] = value

    def __len__(self):
        with self._segment.lock:
            self._validate()
            return len(self._segment.buf)

    def read(self, offset: int = 0, size: Optional[int] = None) -> bytes:
        with self._segment.lock:
            self._validate()
            if size is None:
                return bytes(self._segment.buf[offset:])
            return bytes(self._segment.buf[offset : offset + size])

    def write(self, data: bytes, offset: int = 0):
        with self._segment.lock:
            self._validate()
            end = offset + len(data)
            if end > len(self._segment.buf):
                raise ValueError("Write exceeds shared memory segment boundaries.")
            self._segment.buf[offset:end] = data

    def detach(self) -> bool:
        self._detached = True
        return self._manager.shmdt(self._segment.shmid)


class IPCManager:
    """Manager for simulated IPC facilities registered on the Kernel."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.queues: Dict[int, MessageQueue] = {}
        self.key_to_id: Dict[int, int] = {}
        self.shm_segments: Dict[int, SharedMemorySegment] = {}
        self.shm_key_to_id: Dict[int, int] = {}
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

    def shmget(self, key: int, size: int, shmflg: int = 0) -> int:
        """Get or create a shared memory segment ID."""
        if not isinstance(key, int):
            raise TypeError("Segment key must be an integer")
        if not isinstance(size, int):
            raise TypeError("Segment size must be an integer")
        if size <= 0:
            raise ValueError("Segment size must be a positive integer (> 0)")
        if not isinstance(shmflg, int):
            raise TypeError("Segment flags must be an integer")

        current_pid = get_current_pid()
        with self._lock:
            if key == IPC_PRIVATE:
                shmid = next(self._id_iter)
                memory = self.kernel.drivers.drivers.get("memory")
                if memory:
                    size_kb = (size + 1023) // 1024
                    if not memory.alloc(-shmid, size_kb):
                        raise MemoryError(
                            "Not enough memory available for shared segment."
                        )
                self.shm_segments[shmid] = SharedMemorySegment(
                    shmid, key, current_pid, size
                )
                return shmid

            if key in self.shm_key_to_id:
                shmid = self.shm_key_to_id[key]
                segment = self.shm_segments[shmid]
                if size > segment.size:
                    raise ValueError("Requested size exceeds size of existing segment.")
                if (shmflg & IPC_CREAT) and (shmflg & IPC_EXCL):
                    raise FileExistsError(
                        f"Shared memory segment with key {key} already exists."
                    )
                return shmid
            else:
                if shmflg & IPC_CREAT:
                    shmid = next(self._id_iter)
                    memory = self.kernel.drivers.drivers.get("memory")
                    if memory:
                        size_kb = (size + 1023) // 1024
                        if not memory.alloc(-shmid, size_kb):
                            raise MemoryError(
                                "Not enough memory available for shared segment."
                            )
                    self.shm_segments[shmid] = SharedMemorySegment(
                        shmid, key, current_pid, size
                    )
                    self.shm_key_to_id[key] = shmid
                    return shmid
                else:
                    raise FileNotFoundError(
                        f"No shared memory segment with key {key} found."
                    )

    def shmat(self, shmid: int, shmflg: int = 0) -> SharedMemoryBuffer:
        """Attach a shared memory segment to the calling process."""
        with self._lock:
            segment = self.shm_segments.get(shmid)
        if not segment:
            raise KeyError(f"Invalid shared memory segment ID: {shmid}")
        current_pid = get_current_pid()
        return segment.attach(current_pid, self)

    def shmdt(self, shmid: int) -> bool:
        """Detach a shared memory segment from the calling process."""
        with self._lock:
            segment = self.shm_segments.get(shmid)
        if not segment:
            raise KeyError(f"Invalid shared memory segment ID: {shmid}")
        current_pid = get_current_pid()
        detached = segment.detach(current_pid)

        # Clean up segment if marked removed and attachments reached 0
        with self._lock:
            if segment.removed and segment.nattch == 0:
                self._destroy_shm_segment(shmid)
        return detached

    def shmctl(self, shmid: int, cmd: str) -> Any:
        """Control shared memory segment behavior."""
        with self._lock:
            segment = self.shm_segments.get(shmid)
        if not segment:
            raise KeyError(f"Invalid shared memory segment ID: {shmid}")

        if cmd == "IPC_RMID":
            with self._lock:
                segment.removed = True
                if segment.nattch == 0:
                    self._destroy_shm_segment(shmid)
            return True
        elif cmd == "IPC_STAT":
            with segment.lock:
                return {
                    "shmid": segment.shmid,
                    "key": segment.key,
                    "creator_pid": segment.creator_pid,
                    "size": segment.size,
                    "nattch": segment.nattch,
                    "last_attach_time": segment.last_attach_time,
                    "last_detach_time": segment.last_detach_time,
                    "last_attach_pid": segment.last_attach_pid,
                    "last_detach_pid": segment.last_detach_pid,
                    "removed": segment.removed,
                }
        else:
            raise ValueError(f"Unknown shmctl command: {cmd}")

    def _destroy_shm_segment(self, shmid: int):
        """Internal helper to release SHM segment and free memory."""
        segment = self.shm_segments.pop(shmid, None)
        if segment:
            if segment.key != IPC_PRIVATE:
                self.shm_key_to_id.pop(segment.key, None)
            memory = self.kernel.drivers.drivers.get("memory")
            if memory:
                size_kb = (segment.size + 1023) // 1024
                memory.free(pid=-shmid, size_kb=size_kb)
