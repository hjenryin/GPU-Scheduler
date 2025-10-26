# GPU Scheduler - User API Reference

Version: 0.1.0
Last Updated: 2025-10-21

## Table of Contents

1.  [Overview](#overview)
2.  [Starting the Scheduler](#starting-the-scheduler)
3.  [Stopping the Scheduler](#stopping-the-scheduler)
4.  [Cluster Status](#cluster-status)
5.  [Job Submission](#job-submission)
6.  [Python API](#python-api)

---

## Overview

This system provides distributed job scheduling across multiple GPU machines with active GPU monitoring. All commands follow Ray-like patterns and require **no sudo privileges**.

**Key Components:**
- **Head Node**: Central orchestrator that manages job queue and machine registry
- **Worker Nodes**: GPU machines that execute jobs
- **Client Interfaces**:
  - Command-line interface (CLI) for interactive use
  - Python API for programmatic integration
  - HTTP REST API for advanced usage

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
| `--port`          | int    | `8265`       | Port number for head node HTTP API (auto-fallback if occupied)      |
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
| `--graceful-shutdown-timeout` | int  | `60`    | Seconds to wait for jobs to complete during shutdown |

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

# Start head node with automatic port fallback (if 8265 is occupied by other processes)
scheduler start --head --port 8265
# Output: "Port 8265 is already in use by another process"
#         "Searching for an available port..."
#         "Using available port: 8266"

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

# Start head node with custom graceful shutdown timeout
scheduler start --head --graceful-shutdown-timeout=120

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
| `--all`   | flag | false   | Stop all nodes in cluster |

**Examples:**

````bash
# Stop scheduler on current node (graceful shutdown)
scheduler stop

# Stop all nodes in cluster
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

---

## Python API

For programmatic job submission and cluster management, the scheduler provides a Python client API.

### Installation

```bash
pip install gpu-scheduler
```

### Quick Start

```python
from scheduler import SchedulerClient

# Connect to head node
client = SchedulerClient(address="head-node:8265")

# Submit a job
job = client.submit_job(
    script="train.py",
    requirements="2",
    name="my-training-job"
)
print(f"Submitted job {job.job_id}")

# List running jobs
jobs = client.list_jobs(status_filter="running")
for job in jobs:
    print(f"{job.job_id}: {job.name} on {job.assigned_node}")

# Get logs
logs = client.get_job_logs(job.job_id)
print(logs)
```

### API Reference

#### SchedulerClient

```python
from scheduler import SchedulerClient

# Initialize client
client = SchedulerClient(
    address="head-node:8265",  # Optional, auto-detects from config if not provided
    config=None                # Optional Config instance
)
```

#### Submit Job

```python
job = client.submit_job(
    script="train.py",                    # Required: script path
    requirements="2",                     # Required: resource requirements
    name="job-name",                      # Optional: human-readable name
    script_args=["--epochs", "100"],      # Optional: script arguments
    working_dir="/path/to/dir",           # Optional: working directory
    env_vars={"KEY": "value"},            # Optional: environment variables
    dependencies=["job_id1", "job_id2"],  # Optional: job dependencies
    priority=10,                          # Optional: priority (default 0)
)

# Returns Job object with:
# - job.job_id
# - job.status (JobStatus enum)
# - job.submitted_at
# - job.assigned_node
# - job.assigned_gpus
```

#### List Jobs

```python
jobs = client.list_jobs(
    status_filter="running",  # Optional: "pending", "running", "completed", "failed", "cancelled"
    limit=50                  # Optional: max number of jobs to return
)
# Returns list of Job objects
```

#### Get Job Details

```python
job = client.get_job(job_id="job_abc123")
print(f"Status: {job.status}")
print(f"Node: {job.assigned_node}")
print(f"GPUs: {job.assigned_gpus}")
print(f"Runtime: {job.runtime()}")  # Returns timedelta or None
```

#### Cancel Job

```python
client.cancel_job(job_id="job_abc123")
```

#### Get Job Logs

```python
# Get all logs
logs = client.get_job_logs(job_id="job_abc123")

# Get last 100 lines
logs = client.get_job_logs(job_id="job_abc123", lines=100)

# Get stderr instead of stdout
logs = client.get_job_logs(job_id="job_abc123", stderr=True)
```

#### Stream Job Logs

```python
# Real-time log streaming
for line in client.stream_job_logs(job_id="job_abc123"):
    print(line)
```

#### List Nodes

```python
nodes = client.list_nodes()
for node in nodes:
    print(f"{node.node_name}: {node.num_gpus} GPUs")
    for gpu in node.gpus:
        print(f"  GPU {gpu.gpu_id}: {gpu.stats.utilization}% util")
```

#### Get Node Details

```python
node = client.get_node(node_name="gpu-server-01")
print(f"Connected: {node.status == NodeStatus.CONNECTED}")
print(f"Free GPUs: {len(node.get_free_gpus())}")
```

#### Health Check

```python
if client.health_check():
    print("Head node is healthy")
else:
    print("Head node is unreachable")
```

### Exception Handling

```python
from scheduler import (
    ConnectionException,
    JobNotFoundException,
    NodeNotFoundException,
    ValidationException
)

try:
    job = client.submit_job("train.py", "invalid-req")
except ValidationException as e:
    print(f"Invalid parameters: {e}")
except ConnectionException as e:
    print(f"Cannot connect to head node: {e}")

try:
    job = client.get_job("nonexistent_id")
except JobNotFoundException as e:
    print(f"Job not found: {e}")
```

### Data Models

The Python API exposes these data models:

```python
from scheduler import (
    Job,              # Job information
    Node,             # Node information
    GPU,              # GPU information
    JobRequirement,   # Resource requirements
    JobStatus,        # Enum: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    NodeStatus        # Enum: CONNECTED, DISCONNECTED
)

# Example: Check job status
if job.status == JobStatus.RUNNING:
    print(f"Job is running on {job.assigned_node}")

# Example: Parse requirements
req = JobRequirement("gpu1:2,gpu2:4")
print(req.alternatives)  # [{'node': 'gpu1', 'num_gpus': 2}, {'node': 'gpu2', 'num_gpus': 4}]
```

### Configuration

The client uses the same configuration as the CLI:

```python
from scheduler import Config, load_config

# Load from default location (~/.scheduler/config.yaml)
config = load_config()

# Create custom config
config = Config.from_dict({
    "head_node": {
        "host": "custom-head",
        "port": 9000
    }
})

# Use with client
client = SchedulerClient(config=config)
```

### Example: Batch Job Submission

```python
from scheduler import SchedulerClient

client = SchedulerClient(address="head:8265")

# Submit multiple jobs with dependencies
jobs = []
for i in range(5):
    job = client.submit_job(
        script=f"experiment_{i}.py",
        requirements="2",
        name=f"exp-{i}",
        env_vars={"EXPERIMENT_ID": str(i)}
    )
    jobs.append(job)
    print(f"Submitted {job.job_id}")

# Submit analysis job that depends on all experiments
analysis_job = client.submit_job(
    script="analyze_results.py",
    requirements="1",
    dependencies=[job.job_id for job in jobs],
    name="analysis"
)
print(f"Submitted analysis job {analysis_job.job_id} (depends on {len(jobs)} jobs)")
```

### Example: Monitoring Loop

```python
from scheduler import SchedulerClient, JobStatus
import time

client = SchedulerClient()

job = client.submit_job("train.py", "4", name="training")
print(f"Submitted {job.job_id}")

# Monitor until completion
while True:
    job = client.get_job(job.job_id)

    if job.status == JobStatus.COMPLETED:
        print(f"Job completed successfully (exit code: {job.exit_code})")
        print(client.get_job_logs(job.job_id, lines=20))
        break
    elif job.status == JobStatus.FAILED:
        print(f"Job failed: {job.error_message}")
        break
    elif job.status == JobStatus.RUNNING:
        print(f"Running on {job.assigned_node}, GPUs {job.assigned_gpus}")
    else:
        print(f"Status: {job.status}")

    time.sleep(5)
```

### Example: Integration with ML Pipeline

```python
from scheduler import SchedulerClient
import mlflow

client = SchedulerClient()

# Submit training job
job = client.submit_job(
    script="train.py",
    requirements="4",
    env_vars={
        "MLFLOW_TRACKING_URI": mlflow.get_tracking_uri(),
        "MLFLOW_EXPERIMENT_ID": "123"
    }
)

# Log to MLflow
with mlflow.start_run():
    mlflow.log_param("scheduler_job_id", job.job_id)
    mlflow.log_param("gpus_requested", 4)
    mlflow.set_tag("scheduler_node", job.assigned_node or "pending")
```
