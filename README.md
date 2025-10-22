# GPU Scheduler - User API Reference

Version: 0.1.0
Last Updated: 2025-10-21

## Table of Contents

1.  [Overview](#overview)
2.  [Starting the Scheduler](#starting-the-scheduler)
3.  [Stopping the Scheduler](#stopping-the-scheduler)
4.  [Cluster Status](#cluster-status)
5.  [Job Submission](#job-submission)

---

## Overview

This system provides distributed job scheduling across multiple GPU machines with active GPU monitoring. All commands follow Ray-like patterns and require **no sudo privileges**.

**Key Components:**
- **Head Node**: Central orchestrator that manages job queue and machine registry
- **Worker Nodes**: GPU machines that execute jobs
- **Client CLI**: Command-line interface for job submission and monitoring

**No Sudo Required**: All operations use user-space directories (`~/.scheduler/`) and ports >= 1024.

### Design Philosophy

**1. Ray-Inspired Interface**
- Familiar CLI patterns for Ray users
- `scheduler start --head` / `scheduler start --address=...`
- Simple, consistent command structure

**2. Active GPU Monitoring**
- Polls GPU utilization in real-time
- Designed for **shared GPU environments**
- Works alongside other users' jobs
- Cannot enforce isolation, but monitors and schedules intelligently

**3. Robust Scheduling**
- **Stability Detection**: GPUs must be stable (below threshold for 30s) before considered free
- **Grace Periods**: Nodes don't accept new jobs for 120s after a job starts
- **Conservative**: Prevents conflicts and false positives

**4. No System Privileges**
- No sudo/root required
- No system-level GPU isolation
- Relies on CUDA_VISIBLE_DEVICES compliance
- All files in `~/.scheduler/`

**5. HTTP-Based Communication**
- No SSH between machines
- Workers pull jobs (long-polling)
- Survives network disconnections
- Easy to debug with curl/browser

### Important Limitations

⚠️ **CUDA_VISIBLE_DEVICES Compliance**: Not all frameworks respect `CUDA_VISIBLE_DEVICES`. The scheduler cannot prevent code from using all GPUs. Users should verify their code respects GPU assignments or configure GPU visibility manually in their scripts.

⚠️ **Shared Environment**: This scheduler monitors but cannot prevent other users from starting jobs outside the system. Grace periods and stability detection help minimize conflicts.

⚠️ **Best Effort**: This is a coordination system, not an enforcement system. It works well when users cooperate and code respects GPU assignments.

---

## Starting the Scheduler

### `scheduler start`

Start the scheduler. Automatically detects whether to start as head node or worker node.

**Usage:**
````bash
scheduler start [OPTIONS]
````

**Options:**

| Option            | Type   | Default      | Description                                                         |
| ----------------- | ------ | ------------ | ------------------------------------------------------------------- |
| `--head`          | flag   | false        | Start as head node (orchestrator)                                   |
| `--address`       | url    | -            | Address of head node (for worker nodes). Format: `host:port`       |
| `--port`          | int    | `8265`       | Port number for head node HTTP API                                  |
| `--node-name`     | string | hostname     | Unique identifier for this node                                     |
| `--num-gpus`      | int    | auto-detect  | Number of GPUs on this node (auto-detected from nvidia-smi)        |
| `--temp-dir`      | path   | `~/.scheduler/tmp` | Temporary directory for this node                                 |
| `--log-dir`       | path   | `~/.scheduler/logs` | Directory for logs                                                  |
| `--block`         | flag   | true         | Block until scheduler is stopped (false to run in background)        |
| `--log-level`     | choice | `INFO`       | Logging level: DEBUG, INFO, WARNING, ERROR                         |

**Head Node Specific Options:**

| Option                | Type | Default | Description                                  |
| --------------------- | ---- | ------- | -------------------------------------------- |
| `--heartbeat-timeout` | int  | `60`    | Seconds before marking node as disconnected |
| `--scheduling-interval` | int  | `5`     | Seconds between scheduling cycles            |

**Worker Node Specific Options:**

| Option              | Type | Default | Description                                                        |
| ------------------- | ---- | ------- | ------------------------------------------------------------------ |
| `--gpu-poll-interval` | int  | `10`    | Seconds between GPU status checks                                  |
| `--gpu-util-threshold` | int  | `10`    | GPU utilization % below which GPU is considered free              |
| `--gpu-mem-threshold` | int  | `10`    | GPU memory % below which GPU is considered free                   |
| `--gpu-stable-time` | int  | `30`    | Seconds GPU must stay below threshold before considered free       |
| `--job-startup-grace` | int  | `120`   | Seconds to wait after job starts before scheduling new jobs on same node |

**Examples:**

````bash
# Start head node
scheduler start --head

# Start head node on custom port
scheduler start --head --port 9000

# Start worker node connecting to head
scheduler start --address=192.168.1.100:8265

# Start worker with custom node name
scheduler start --address=head.local:8265 --node-name=gpu-server-01

# Start worker with manual GPU specification
scheduler start --address=head.local:8265 --num-gpus=8

# Start worker with conservative GPU detection
scheduler start --address=head.local:8265 \
                --gpu-util-threshold=5 \
                --gpu-stable-time=60 \
                --job-startup-grace=180

# Start in background (non-blocking)
scheduler start --head --block=false
````

---

## Stopping the Scheduler

### `scheduler stop`

Stop the scheduler on the current node.

**Usage:**
````bash
scheduler stop [OPTIONS]
````

**Options:**

| Option    | Type | Default | Description                      |
| --------- | ---- | ------- | -------------------------------- |
| `--force` | flag | false   | Force stop without graceful shutdown |
| `--all`   | flag | false   | Stop all nodes in the cluster (head only) |

**Examples:**

````bash
# Stop scheduler on current node
scheduler stop

# Force stop (kill immediately)
scheduler stop --force

# Stop all nodes in cluster (run from head node)
scheduler stop --all
````

---

## Cluster Status

### `scheduler status`

Interactive TUI (terminal user interface) for monitoring cluster status, nodes, and jobs. Similar to `nvitop` but for the entire cluster.

**Usage:**
````bash
scheduler status
````

**No Options Required**: The command automatically connects to the head node (either running locally or using the configured address in `~/.scheduler/config.yaml`).

---

## Job Submission

### `scheduler submit`

Submit a new job to the scheduler.

**Usage:**
````bash
scheduler submit [OPTIONS] SCRIPT [-- SCRIPT_ARGS...]
````

**Positional Arguments:**

| Argument      | Description                                     |
| ------------- | ----------------------------------------------- |
| `SCRIPT`      | Path to the script to execute (Python, bash, etc.) |
| `SCRIPT_ARGS` | Arguments to pass to the script (after `--`)      |

**Options:**

| Option        | Type   | Default    | Description                                               |
| ------------- | ------ | ---------- | --------------------------------------------------------- |
| `--req`       | string | `1`        | Resource requirements (see format below)                  |
| `--depends-on` | list   | none       | Comma-separated list of job IDs this job depends on        |
| `--name`      | string | script name | Human-readable job name                                   |
| `--priority`  | int    | `0`        | Job priority (higher = more important)                     |
| `--env`       | list   | none       | Environment variables (KEY=VALUE format, can be repeated) |
| `--timeout`   | int    | none       | Job timeout in seconds                                   |
| `--working-dir` | path | current dir | Working directory for job execution                         |
| `--async`     | flag   | false      | Submit and return immediately without waiting              |
| `--log-to-driver` | flag | false  | Stream logs to stdout in real-time                 |

**Resource Requirement Format (`--req`):**

The `--req` flag supports flexible resource specifications:

| Format        | Meaning                             | Example           |
| ------------- | ----------------------------------- | ----------------- |
| `N`           | N GPUs on any available node        | ``--req 2``       |
| `node1:N`     | N GPUs on node1 specifically        | ``--req gpu1:2``  |
| `node1:N,node2:M` | N GPUs on node1 OR M GPUs on node2 | ``--req gpu1:2,gpu2:4`` |

**Examples:**

````bash
# Simple job requiring 2 GPUs on any node
scheduler submit --req 2 train.py

# Job requiring 4 GPUs specifically on gpu1
scheduler submit --req gpu1:4 train.py

# Job that can run on either gpu1 (2 GPUs) or gpu2 (4 GPUs)
scheduler submit --req gpu1:2,gpu2:4 train.py

# Job with dependencies (waits for job_123 and job_456 to complete)
scheduler submit --req 2 --depends-on job_123,job_456 train_stage2.py

# Job with custom name and environment variables
scheduler submit --req 4 \
                 --name "bert-training" \
                 --env WANDB_API_KEY=xyz123 \
                 --env DATASET_PATH=/data/bert \
                 train.py

# Job with script arguments
scheduler submit --req 2 train.py -- --epochs 100 --batch-size 32

# Submit and stream logs
scheduler submit --req 1 --log-to-driver train.py

# Submit asynchronously
scheduler submit --req 2 --async train.py

# Job with timeout
scheduler submit --req 4 --timeout 3600 train.py
````

**Output:**
````text
Job submitted successfully!
Job ID: job_abc123def456
Status: pending
Requirements: 2 GPUs on any node
View status: scheduler status (then press 'J' and search for job)
````

**Job ID Assignment:**
The command returns the job ID which can be captured:
````bash
JOB_ID=$(scheduler submit --req 2 --async train.py | grep "Job ID" | awk '{print $3}')
echo $JOB_ID  # job_abc123def456
````