"""IPC diagnostic commands: ipcs and ipcrm."""

import time as _time
from typing import List

from .base import Command


class IpcsCommand(Command):
    """Report Inter-Process Communication facilities status."""

    name = "ipcs"
    usage = "ipcs [-q] [-m] [-t] [-p]"
    description = "Report Inter-Process Communication facilities status."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        show_queues = False
        show_shm = False
        show_times = False
        show_pids = False

        has_type_option = False
        for arg in parts[1:]:
            if arg == "-q":
                show_queues = True
                has_type_option = True
            elif arg == "-m":
                show_shm = True
                has_type_option = True
            elif arg == "-t":
                show_times = True
            elif arg == "-p":
                show_pids = True
            else:
                print(f"ipcs: invalid option -- '{arg}'")
                print("Usage: ipcs [-q] [-m] [-t] [-p]")
                return False

        if not has_type_option:
            show_queues = True
            show_shm = True

        lines = []
        if show_queues:
            lines.append("------ Message Queues ------")

            # Thread-safe copy under the IPCManager lock
            with self.kernel.ipc._lock:
                queues = list(self.kernel.ipc.queues.values())

            if show_times:
                lines.append(
                    f"{'key':<12} {'msqid':<8} {'last-send':<20} {'last-recv':<20}"
                )
                for q in queues:
                    with q.lock:
                        send_time = (
                            _time.strftime(
                                "%Y-%m-%d %H:%M:%S", _time.localtime(q.last_snd_time)
                            )
                            if q.last_snd_time
                            else "no-entry"
                        )
                        recv_time = (
                            _time.strftime(
                                "%Y-%m-%d %H:%M:%S", _time.localtime(q.last_rcv_time)
                            )
                            if q.last_rcv_time
                            else "no-entry"
                        )
                        key_str = f"0x{q.key:08x}" if q.key >= 0 else str(q.key)
                        lines.append(
                            f"{key_str:<12} {q.msqid:<8} "
                            f"{send_time:<20} {recv_time:<20}"
                        )
            elif show_pids:
                lines.append(
                    f"{'key':<12} {'msqid':<8} {'owner':<8} {'lspid':<8} {'lrpid':<8}"
                )
                for q in queues:
                    with q.lock:
                        key_str = f"0x{q.key:08x}" if q.key >= 0 else str(q.key)
                        lines.append(
                            f"{key_str:<12} {q.msqid:<8} {q.creator_pid:<8} "
                            f"{q.last_snd_pid:<8} {q.last_rcv_pid:<8}"
                        )
            else:
                lines.append(
                    f"{'key':<12} {'msqid':<8} {'owner':<8} "
                    f"{'messages':<10} {'bytes':<10}"
                )
                for q in queues:
                    with q.lock:
                        key_str = f"0x{q.key:08x}" if q.key >= 0 else str(q.key)
                        msg_count = len(q.messages)
                        msg_bytes = sum(len(msg.text) for msg in q.messages)
                        lines.append(
                            f"{key_str:<12} {q.msqid:<8} {q.creator_pid:<8} "
                            f"{msg_count:<10} {msg_bytes:<10}"
                        )

        if show_shm:
            if lines:
                lines.append("")
            lines.append("------ Shared Memory Segments ------")

            with self.kernel.ipc._lock:
                shm_segments = list(self.kernel.ipc.shm_segments.values())

            if show_times:
                lines.append(
                    f"{'key':<12} {'shmid':<8} {'last-attach':<20} {'last-detach':<20}"
                )
                for s in shm_segments:
                    with s.lock:
                        attach_time = (
                            _time.strftime(
                                "%Y-%m-%d %H:%M:%S", _time.localtime(s.last_attach_time)
                            )
                            if s.last_attach_time
                            else "no-entry"
                        )
                        detach_time = (
                            _time.strftime(
                                "%Y-%m-%d %H:%M:%S", _time.localtime(s.last_detach_time)
                            )
                            if s.last_detach_time
                            else "no-entry"
                        )
                        key_str = f"0x{s.key:08x}" if s.key >= 0 else str(s.key)
                        lines.append(
                            f"{key_str:<12} {s.shmid:<8} "
                            f"{attach_time:<20} {detach_time:<20}"
                        )
            elif show_pids:
                lines.append(
                    f"{'key':<12} {'shmid':<8} {'owner':<8} {'cpid':<8} {'lpid':<8}"
                )
                for s in shm_segments:
                    with s.lock:
                        key_str = f"0x{s.key:08x}" if s.key >= 0 else str(s.key)
                        lines.append(
                            f"{key_str:<12} {s.shmid:<8} {s.creator_pid:<8} "
                            f"{s.creator_pid:<8} {s.last_attach_pid:<8}"
                        )
            else:
                lines.append(
                    f"{'key':<12} {'shmid':<8} {'owner':<8} "
                    f"{'perms':<8} {'size':<10} {'nattch':<8} {'status':<8}"
                )
                for s in shm_segments:
                    with s.lock:
                        key_str = f"0x{s.key:08x}" if s.key >= 0 else str(s.key)
                        status_str = "dest" if s.removed else ""
                        lines.append(
                            f"{key_str:<12} {s.shmid:<8} {s.creator_pid:<8} "
                            f"{'666':<8} {s.size:<10} {s.nattch:<8} {status_str:<8}"
                        )

        out = "\n".join(lines)
        return self.emit(out, capture_output)


class IpcrmCommand(Command):
    """Remove certain IPC resources."""

    name = "ipcrm"
    usage = "ipcrm [-q msqid] [-Q msgkey] [-m shmid] [-M shmkey]"
    description = "Remove certain IPC resources."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: ipcrm [-q msqid] [-Q msgkey] [-m shmid] [-M shmkey]")
            return False

        opt = parts[1]
        arg = parts[2]

        if opt == "-q":
            try:
                msqid = int(arg)
            except ValueError:
                print(f"ipcrm: invalid message queue ID: {arg}")
                return False

            try:
                ok = self.kernel.ipc.msgctl(msqid, "IPC_RMID")
            except KeyError:
                ok = False

            if ok:
                print(f"Message queue ID {msqid} removed.")
                return True
            else:
                print(f"ipcrm: failed to remove queue ID {msqid}: not found.")
                return False

        elif opt == "-Q":
            try:
                if arg.startswith("0x") or arg.startswith("0X"):
                    key = int(arg, 16)
                else:
                    key = int(arg)
            except ValueError:
                print(f"ipcrm: invalid message queue key: {arg}")
                return False

            with self.kernel.ipc._lock:
                msqid = self.kernel.ipc.key_to_id.get(key)
                if msqid is None:
                    for q in self.kernel.ipc.queues.values():
                        if q.key == key:
                            msqid = q.msqid
                            break

            if msqid is not None:
                try:
                    ok = self.kernel.ipc.msgctl(msqid, "IPC_RMID")
                except KeyError:
                    ok = False
                if ok:
                    print(f"Message queue with key {arg} removed.")
                    return True
            print(f"ipcrm: failed to remove queue key {arg}: not found.")
            return False

        elif opt == "-m":
            try:
                shmid = int(arg)
            except ValueError:
                print(f"ipcrm: invalid shared memory segment ID: {arg}")
                return False

            try:
                ok = self.kernel.ipc.shmctl(shmid, "IPC_RMID")
            except KeyError:
                ok = False

            if ok:
                print(f"Shared memory segment ID {shmid} removed.")
                return True
            else:
                print(f"ipcrm: failed to remove shared memory ID {shmid}: not found.")
                return False

        elif opt == "-M":
            try:
                if arg.startswith("0x") or arg.startswith("0X"):
                    key = int(arg, 16)
                else:
                    key = int(arg)
            except ValueError:
                print(f"ipcrm: invalid shared memory key: {arg}")
                return False

            with self.kernel.ipc._lock:
                shmid = self.kernel.ipc.shm_key_to_id.get(key)
                if shmid is None:
                    for s in self.kernel.ipc.shm_segments.values():
                        if s.key == key:
                            shmid = s.shmid
                            break

            if shmid is not None:
                try:
                    ok = self.kernel.ipc.shmctl(shmid, "IPC_RMID")
                except KeyError:
                    ok = False
                if ok:
                    print(f"Shared memory segment with key {arg} removed.")
                    return True
            print(f"ipcrm: failed to remove shared memory key {arg}: not found.")
            return False

        else:
            print(f"ipcrm: invalid option -- '{opt}'")
            print("Usage: ipcrm [-q msqid] [-Q msgkey] [-m shmid] [-M shmkey]")
            return False


def register_ipc_commands(registry):
    """Register IPC commands with the registry."""
    registry.register(IpcsCommand(registry.kernel))
    registry.register(IpcrmCommand(registry.kernel))
