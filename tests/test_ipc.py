import time
import pytest
import threading

from pureos.kernel import Kernel
from pureos.ipc import IPC_CREAT, IPC_EXCL, IPC_PRIVATE


@pytest.fixture
def kernel():
    k = Kernel()
    k.initialize()
    yield k
    k.shutdown()


def test_msgget_creation_and_lookup(kernel):
    ipc = kernel.ipc

    # Test key without IPC_CREAT raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        ipc.msgget(1234, 0)

    # Test key with IPC_CREAT creates a queue
    msqid = ipc.msgget(1234, IPC_CREAT)
    assert msqid > 0

    # Test key lookup returns the same queue
    assert ipc.msgget(1234, 0) == msqid
    assert ipc.msgget(1234, IPC_CREAT) == msqid

    # Test IPC_EXCL raising FileExistsError
    with pytest.raises(FileExistsError):
        ipc.msgget(1234, IPC_CREAT | IPC_EXCL)

    # Test IPC_PRIVATE always creates a new unique queue
    priv_id1 = ipc.msgget(IPC_PRIVATE)
    priv_id2 = ipc.msgget(IPC_PRIVATE)
    assert priv_id1 != priv_id2
    assert priv_id1 != msqid
    assert priv_id2 != msqid


def test_msgsnd_msgrcv_filtering(kernel):
    ipc = kernel.ipc
    msqid = ipc.msgget(1234, IPC_CREAT)

    # Send messages of different types
    ipc.msgsnd(msqid, msg_type=10, text="Msg10")
    ipc.msgsnd(msqid, msg_type=20, text="Msg20")
    ipc.msgsnd(msqid, msg_type=5, text="Msg5")

    # Receive with type 20
    res = ipc.msgrcv(msqid, msg_type=20, block=False)
    assert res is not None
    assert res[0] == 20
    assert res[1] == "Msg20"

    # Receive with type 0 (FIFO, should be Msg10 since Msg20 was consumed)
    res = ipc.msgrcv(msqid, msg_type=0, block=False)
    assert res is not None
    assert res[0] == 10
    assert res[1] == "Msg10"

    # Receive with type < 0 (receive lowest type <= abs(type))
    # Send Msg15 to test sorting
    ipc.msgsnd(msqid, msg_type=15, text="Msg15")
    # Queue currently has: Msg5 (type 5), Msg15 (type 15)
    # Receive with msg_type = -15. Absolute value is 15.
    # Matching types are 5 and 15. The lowest type is 5.
    res = ipc.msgrcv(msqid, msg_type=-15, block=False)
    assert res is not None
    assert res[0] == 5
    assert res[1] == "Msg5"

    res = ipc.msgrcv(msqid, msg_type=-15, block=False)
    assert res is not None
    assert res[0] == 15
    assert res[1] == "Msg15"

    # Queue should be empty now
    assert ipc.msgrcv(msqid, msg_type=0, block=False) is None


def test_msgctl_commands(kernel):
    ipc = kernel.ipc
    msqid = ipc.msgget(5678, IPC_CREAT)

    ipc.msgsnd(msqid, 2, "hello")
    ipc.msgsnd(msqid, 4, "world")

    # Check stats
    stats = ipc.msgctl(msqid, "IPC_STAT")
    assert stats["msqid"] == msqid
    assert stats["key"] == 5678
    assert stats["msg_qnum"] == 2
    assert stats["msg_bytes"] == 10

    # Remove queue
    ok = ipc.msgctl(msqid, "IPC_RMID")
    assert ok is True

    # Stats/lookup should fail now
    with pytest.raises(KeyError):
        ipc.msgctl(msqid, "IPC_STAT")

    with pytest.raises(FileNotFoundError):
        ipc.msgget(5678, 0)


def test_ipcs_ipcrm_shell_commands(kernel):
    shell = kernel.shell
    ipc = kernel.ipc

    # Ensure clean state
    ipc.queues.clear()
    ipc.key_to_id.clear()

    # Empty ipcs command output
    out = shell.registry.execute(["ipcs"], capture_output=True)
    assert "------ Message Queues ------" in out

    # Create queues
    msqid1 = ipc.msgget(0x111, IPC_CREAT)
    msqid2 = ipc.msgget(IPC_PRIVATE)

    ipc.msgsnd(msqid1, 1, "test")

    # Test basic ipcs command
    out = shell.registry.execute(["ipcs"], capture_output=True)
    assert "0x00000111" in out
    assert str(msqid1) in out
    assert str(msqid2) in out

    # Test ipcs -t (timestamps)
    out_t = shell.registry.execute(["ipcs", "-t"], capture_output=True)
    assert "last-send" in out_t
    assert "last-recv" in out_t

    # Test ipcs -p (PIDs)
    out_p = shell.registry.execute(["ipcs", "-p"], capture_output=True)
    assert "lspid" in out_p
    assert "lrpid" in out_p

    # Test ipcrm -q (remove by ID)
    res = shell.execute(f"ipcrm -q {msqid2}")
    assert res is True
    assert msqid2 not in ipc.queues

    # Test ipcrm -Q (remove by key)
    res = shell.execute("ipcrm -Q 0x111")
    assert res is True
    assert msqid1 not in ipc.queues


def test_ipc_blocking_synchronization(kernel):
    ipc = kernel.ipc
    msqid = ipc.msgget(9999, IPC_CREAT)

    received_payload = []

    def receiver(stop_event=None):
        # Blocking receive
        msg = ipc.msgrcv(msqid, msg_type=42, block=True, timeout=2.0)
        if msg:
            received_payload.append(msg[1])

    # Spawn receiver process
    p = kernel.scheduler.spawn("recv_proc", target_func=receiver)

    # Let the thread enter wait block
    time.sleep(0.1)

    # Send message from main thread
    ipc.msgsnd(msqid, msg_type=42, text="woken_up")

    # Wait for receiver process
    kernel.scheduler.wait(p.pid, timeout=2.0)

    assert "woken_up" in received_payload


def test_removed_queue_unblocks_receiver(kernel):
    ipc = kernel.ipc
    msqid = ipc.msgget(777, IPC_CREAT)

    raised = []

    def receiver():
        try:
            ipc.msgrcv(msqid, msg_type=0, block=True)
        except OSError as e:
            raised.append(e)

    t = threading.Thread(target=receiver, daemon=True)
    t.start()

    time.sleep(0.1)

    # Remove queue while thread is blocked on msgrcv
    ipc.msgctl(msqid, "IPC_RMID")
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert len(raised) == 1
    assert "removed" in str(raised[0])


def test_queue_capacity_limit(kernel):
    ipc = kernel.ipc
    msqid = ipc.msgget(888, IPC_CREAT)
    queue = ipc.queues[msqid]
    # Set maximum queue bytes capacity to 10 bytes
    queue.max_bytes = 10

    # Send 8 bytes - should succeed
    assert ipc.msgsnd(msqid, 1, "12345678", block=False) is True

    # Send 5 more bytes - should raise BlockingIOError (8 + 5 = 13 > 10)
    with pytest.raises(BlockingIOError):
        ipc.msgsnd(msqid, 1, "12345", block=False)

    # Receive first message to free space
    res = ipc.msgrcv(msqid, 0, block=False)
    assert res is not None

    # Send 5 bytes now - should succeed
    assert ipc.msgsnd(msqid, 1, "12345", block=False) is True


def test_type_and_value_validations(kernel):
    ipc = kernel.ipc

    with pytest.raises(TypeError):
        ipc.msgget("invalid_key", IPC_CREAT)

    msqid = ipc.msgget(999, IPC_CREAT)

    with pytest.raises(TypeError):
        ipc.msgsnd(msqid, "invalid_type", "text")

    with pytest.raises(ValueError):
        ipc.msgsnd(msqid, -5, "text")

    with pytest.raises(TypeError):
        ipc.msgsnd(msqid, 1, 12345)
