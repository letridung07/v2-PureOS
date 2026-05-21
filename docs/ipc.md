# Inter-Process Communication (IPC)

v2-PureOS implements a simulated System V IPC subsystem, providing mechanisms for processes to communicate and synchronize.

## Overview

The IPC subsystem (`pureos.ipc`) is managed by the `IPCManager` registered on the Kernel. It supports two main types of IPC:
1. **Message Queues**: For passing discrete messages between processes.
2. **Shared Memory**: For high-performance data sharing via a common memory segment.

## 1. Message Queues

Message queues allow processes to send and receive formatted messages. Each queue is identified by a unique `msqid` and can be optionally associated with a `key`.

### Concepts
- **Key**: A numeric identifier used to locate or create a queue (e.g., `0x1234`).
- **msgget**: Create or open a queue.
- **msgsnd**: Append a message to a queue.
- **msgrcv**: Retrieve a message from a queue (supports FIFO or type-based selection).
- **msgctl**: Perform control operations (e.g., `IPC_RMID` to remove a queue).

### Type-based Retrieval
`msgrcv` allows filtering by `msg_type`:
- `0`: Receive the first message (FIFO).
- `>0`: Receive the first message of exactly this type.
- `<0`: Receive the first message with type <= absolute value of `msg_type`.

## 2. Shared Memory

Shared memory allows multiple processes to map the same physical memory segment into their "virtual" address space.

### Concepts
- **shmget**: Create or open a shared memory segment.
- **shmat**: Attach a segment to the current process, returning a `SharedMemoryBuffer`.
- **shmdt**: Detach from a segment.
- **shmctl**: Control operations (e.g., `IPC_RMID`).

### SharedMemoryBuffer
The `SharedMemoryBuffer` provides a thread-safe, bytearray-like interface:
- `read(offset, size)`: Read bytes from the segment.
- `write(data, offset)`: Write bytes to the segment.
- `buf[index]`: Access individual bytes.

## 3. IPC Commands

The shell provides two commands for managing IPC resources:

### `ipcs` — Report IPC Status
```text
ipcs [-q] [-m] [-t] [-p]
```
- `-q`: Show message queues.
- `-m`: Show shared memory segments.
- `-t`: Show last access times.
- `-p`: Show PIDs of creators and last actors.

### `ipcrm` — Remove IPC Resources
```text
ipcrm [-q msqid] [-Q msgkey] [-m shmid] [-M shmkey]
```
- `-q / -Q`: Remove a message queue by ID or key.
- `-m / -M`: Remove a shared memory segment by ID or key.

## 4. Resource Limits

- **Message Queues**: Default capacity is 16KB per queue.
- **Shared Memory**: Total size is limited by the system's available memory (RAM + Swap) as tracked by the `MemoryDriver`.
