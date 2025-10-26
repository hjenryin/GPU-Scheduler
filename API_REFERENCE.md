# GPU Scheduler - User API Reference

Version: 0.1.0  
Last Updated: 2025-10-21

## Table of Contents

1. [Overview](#overview)
2. [Starting the Scheduler](#starting-the-scheduler)
3. [Stopping the Scheduler](#stopping-the-scheduler)
4. [Cluster Status](#cluster-status)
5. [Job Submission](#job-submission)
6. [Job Management](#job-management)
7. [Configuration](#configuration)
8. [Environment Variables](#environment-variables)
9. [Python API](#python-api)
10. [HTTP API Reference (Advanced)](#api-endpoint-reference-advanced)

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
```bash
scheduler start [OPTIONS]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--head` | flag | false | Start as head node (orchestrator) |
| `--address` | url | - | Address of head node (for worker nodes). Format: `host:port` |
| `--port` | int | `8265` | Port number for head node HTTP API |
| `--node-name` | string | hostname | Unique identifier for this node |
| `--num-gpus` | int | auto-detect | Number of GPUs on this node (auto-detected from nvidia-smi) |
| `--temp-dir` | path | `~/.scheduler/tmp` | Temporary directory for this node |
| `--log-dir` | path | `~/.scheduler/logs` | Directory for logs |
| `--block` | flag | true | Block until scheduler is stopped (false to run in background) |
| `--log-level` | choice | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |

**Head Node Specific Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--heartbeat-timeout` | int | `60` | Seconds before marking node as disconnected |
| `--scheduling-interval` | int | `5` | Seconds between scheduling cycles |
| `--graceful-shutdown-timeout` | int | `60` | Seconds to wait for jobs to complete during shutdown |

**Worker Node Specific Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gpu-poll-interval` | int | `10` | Seconds between GPU status checks |
| `--gpu-util-threshold` | int | `10` | GPU utilization % below which GPU is considered free |
| `--gpu-mem-threshold` | int | `10` | GPU memory % below which GPU is considered free |
| `--gpu-stable-time` | int | `30` | Seconds GPU must stay below threshold before considered free |
| `--job-startup-grace` | int | `120` | Seconds to wait after job starts before scheduling new jobs on same node |

**Examples:**

```bash
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

# Start head node with custom graceful shutdown timeout
scheduler start --head --graceful-shutdown-timeout=120

# Start in background (non-blocking)
scheduler start --head --block=false
```

**Important Notes on GPU Scheduling:**

1. **CUDA_VISIBLE_DEVICES Limitation**: While jobs are assigned GPUs via the `CUDA_VISIBLE_DEVICES` environment variable, not all code respects this setting. Some frameworks or libraries may attempt to use all available GPUs regardless. The scheduler cannot prevent this at the system level.

2. **Job Startup Grace Period**: When a job starts on a node, the scheduler will not schedule additional jobs on that node for a grace period (default 120 seconds). This prevents:
   - Multiple jobs starting simultaneously and competing for resources
   - Scheduling during model loading or dataset preprocessing phases when GPU utilization is temporarily low

3. **Stable GPU Detection**: A GPU is only considered "free" after its utilization stays below the threshold for a consecutive period (default 30 seconds). This prevents:
   - False positives during brief idle periods
   - Scheduling during data loading gaps
   - Conflicts with newly started jobs from other users

4. **Tuning Recommendations**:
   - Increase `--gpu-stable-time` (e.g., 60s) if you see frequent false positives
   - Increase `--job-startup-grace` (e.g., 300s) if your jobs have long initialization phases
   - Decrease `--gpu-util-threshold` (e.g., 5%) for stricter GPU availability detection
   - Monitor your actual workload patterns and adjust accordingly

**Notes:**
- The first `scheduler start --head` on your network becomes the orchestrator
- All subsequent `scheduler start --address=...` commands connect as workers
- The scheduler automatically detects GPUs using `nvidia-smi` if `--num-gpus` is not specified

---

## Stopping the Scheduler

### `scheduler stop`

Stop the scheduler on the current node.

**Usage:**
```bash
scheduler stop [OPTIONS]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--all` | flag | false | Stop all nodes in cluster |

**Examples:**

```bash
# Stop scheduler on current node (graceful shutdown)
scheduler stop

# Stop all nodes in cluster
scheduler stop --all
```

---

## Cluster Status

### `scheduler status`

Interactive TUI (terminal user interface) for monitoring cluster status, nodes, and jobs. Similar to `nvitop` but for the entire cluster.

**Usage:**
```bash
scheduler status
```

**No Options Required**: The command automatically connects to the head node (either running locally or using the configured address in `~/.scheduler/config.yaml`).

**Interactive Features:**

The TUI provides a real-time dashboard with multiple views:

**Default View - Cluster Overview:**
```
╔════════════════════════════════════════════════════════════════════════════╗
║ GPU Scheduler Cluster - head.local:8265                    [Q]uit [H]elp  ║
╠════════════════════════════════════════════════════════════════════════════╣
║ Nodes: 3 connected, 0 disconnected | GPUs: 16 total, 10 free, 6 in use   ║
║ Jobs: 5 pending, 6 running, 124 completed, 2 failed                       ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║ NODE STATUS                                                                ║
║ ┌──────────┬───────────┬──────┬──────┬───────────┬──────────────────────┐ ║
║ │ Node     │ Status    │ GPUs │ Free │ Running   │ Last Heartbeat       │ ║
║ ├──────────┼───────────┼──────┼──────┼───────────┼──────────────────────┤ ║
║ │ gpu1     │ connected │  4   │  2   │ 2 jobs    │ 2s ago               │ ║
║ │ gpu2     │ connected │  8   │  8   │ 0 jobs    │ 5s ago               │ ║
║ │ gpu3     │ connected │  4   │  0   │ 4 jobs    │ 3s ago               │ ║
║ └──────────┴───────────┴──────┴──────┴───────────┴──────────────────────┘ ║
║                                                                            ║
║ GPU UTILIZATION (press 'G' for detailed GPU view)                         ║
║ gpu1: GPU0 ████████░░ 82%  GPU1 ░░░░░░░░░░  5%  GPU2 ████████░░ 79% ... ║
║ gpu2: GPU0 ░░░░░░░░░░  3%  GPU1 ░░░░░░░░░░  2%  GPU2 ░░░░░░░░░░  1% ... ║
║ gpu3: GPU0 █████████░ 95%  GPU1 █████████░ 91%  GPU2 ████████░░ 88% ... ║
║                                                                            ║
║ ACTIVE JOBS (press 'J' for full job list, Enter to select)                ║
║ ┌─────────────┬──────────────┬─────────┬──────┬────────┬─────────────┐   ║
║ │ Job ID      │ Name         │ Status  │ Node │ GPUs   │ Runtime     │   ║
║ ├─────────────┼──────────────┼─────────┼──────┼────────┼─────────────┤   ║
║ │ job_abc123  │ train.py     │ running │ gpu1 │ 2      │ 00:15:32    │   ║
║ │ job_def456  │ eval.py      │ pending │ -    │ 1      │ -           │   ║
║ │ job_ghi789  │ pretrain.py  │ running │ gpu3 │ 4      │ 02:34:11    │   ║
║ └─────────────┴──────────────┴─────────┴──────┴────────┴─────────────┘   ║
╠════════════════════════════════════════════════════════════════════════════╣
║ [N]odes [J]obs [G]PUs [Q]uit [H]elp [/] Search                            ║
╚════════════════════════════════════════════════════════════════════════════╝
```

**Keyboard Shortcuts:**

| Key | Action |
|-----|--------|
| `N` | Switch to Nodes view (detailed node information) |
| `J` | Switch to Jobs view (full job list with filters) |
| `G` | Switch to GPUs view (detailed per-GPU statistics) |
| `Enter` | Select item for details (job/node) |
| `↑` `↓` | Navigate up/down |
| `PgUp` `PgDn` | Page up/down |
| `/` | Search/filter |
| `R` | Refresh now |
| `C` | Cancel selected job (with confirmation) |
| `L` | View logs for selected job |
| `Q` or `Ctrl+C` | Quit |
| `H` or `?` | Help screen |
| `1-5` | Toggle filters (pending/running/completed/failed/all) |

**Nodes View (press 'N'):**
Shows detailed information about each node:
```
┌────────────────────────────────────────────────────────────────────────┐
│ Node: gpu1                                          [Back: ESC or N]   │
├────────────────────────────────────────────────────────────────────────┤
│ Status: connected                                                      │
│ Address: 192.168.1.101                                                 │
│ Last Heartbeat: 2s ago                                                 │
│ Uptime: 3d 14h 23m                                                     │
│                                                                        │
│ GPUs: 4 total, 2 free, 2 in use                                       │
│ ┌─────┬──────────────┬──────────┬───────────┬─────────┬─────────────┐│
│ │ GPU │ Util         │ Memory   │ Temp      │ Power   │ Job         ││
│ ├─────┼──────────────┼──────────┼───────────┼─────────┼─────────────┤│
│ │ 0   │ ████████░░82%│ 14G/16G  │ 72°C      │ 280W    │ job_abc123  ││
│ │ 1   │ ░░░░░░░░░░5% │  1G/16G  │ 45°C      │  45W    │ -           ││
│ │ 2   │ ████████░░79%│ 13G/16G  │ 69°C      │ 265W    │ job_abc123  ││
│ │ 3   │ ░░░░░░░░░░3% │  1G/16G  │ 43°C      │  42W    │ -           ││
│ └─────┴──────────────┴──────────┴───────────┴─────────┴─────────────┘│
│                                                                        │
│ Running Jobs:                                                          │
│   • job_abc123: train.py (2 GPUs: 0,2) - 00:15:32                    │
│                                                                        │
│ Pending Jobs Eligible for This Node: 2                                │
└────────────────────────────────────────────────────────────────────────┘
```

**Jobs View (press 'J'):**
Shows all jobs with filtering options:
```
┌────────────────────────────────────────────────────────────────────────┐
│ Jobs                                [1]Pending [2]Running [3]Completed  │
│ Filter: [All Jobs ▼] Sort: [Submitted ▼]               [Back: ESC]    │
├────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────┬─────────────┬──────────┬──────┬──────┬─────────────┐ │
│ │ Job ID       │ Name        │ Status   │ Node │ GPUs │ Runtime     │ │
│ ├──────────────┼─────────────┼──────────┼──────┼──────┼─────────────┤ │
│ │► job_abc123  │ train.py    │ running  │ gpu1 │ 2    │ 00:15:32    │ │
│ │  job_def456  │ eval.py     │ pending  │ -    │ 1    │ -           │ │
│ │  job_ghi789  │ pretrain.py │ running  │ gpu3 │ 4    │ 02:34:11    │ │
│ │  job_jkl012  │ finetune.py │ running  │ gpu3 │ 4    │ 01:22:45    │ │
│ │  job_mno345  │ infer.py    │ pending  │ -    │ 2    │ -           │ │
│ │  ...                                                                │ │
│ └──────────────┴─────────────┴──────────┴──────┴──────┴─────────────┘ │
│                                                                        │
│ [Enter] Details  [L] Logs  [C] Cancel  [/] Search                     │
└────────────────────────────────────────────────────────────────────────┘
```

**Job Details (press Enter on a job):**
```
┌────────────────────────────────────────────────────────────────────────┐
│ Job: job_abc123                                     [Back: ESC]        │
├────────────────────────────────────────────────────────────────────────┤
│ Name: train.py                                                         │
│ Status: running                                                        │
│ Node: gpu1                                                             │
│ GPUs: 2 (GPU 0, 2)                                                     │
│ Requirements: gpu1:2,gpu2:2 (matched: gpu1:2)                         │
│ Priority: 0                                                            │
│                                                                        │
│ Submitted: 2025-10-21 10:30:00                                        │
│ Started: 2025-10-21 10:35:12                                          │
│ Runtime: 00:15:32                                                      │
│                                                                        │
│ Script: /home/user/train.py                                           │
│ Working Dir: /home/user/project                                       │
│ Command: python train.py --epochs 100 --batch-size 32                 │
│                                                                        │
│ Dependencies:                                                          │
│   • job_xyz789 (preprocess.py) - completed                            │
│                                                                        │
│ Environment:                                                           │
│   CUDA_VISIBLE_DEVICES=0,2                                            │
│   WANDB_API_KEY=***                                                   │
│                                                                        │
│ [L] View Logs  [C] Cancel Job  [R] Retry  [ESC] Back                  │
└────────────────────────────────────────────────────────────────────────┘
```

**GPUs View (press 'G'):**
Shows detailed GPU statistics across all nodes:
```
┌────────────────────────────────────────────────────────────────────────┐
│ GPU Utilization - All Nodes                         [Back: ESC or G]  │
├────────────────────────────────────────────────────────────────────────┤
│ gpu1 - 4 GPUs (2 free, 2 in use)                                      │
│ ┌──────┬─────────────────────────┬──────────┬────────┬───────────────┐│
│ │ GPU  │ Utilization             │ Memory   │ Temp   │ Job           ││
│ ├──────┼─────────────────────────┼──────────┼────────┼───────────────┤│
│ │ 0    │ ████████████████░░ 82%  │ 14G/16G  │ 72°C   │ job_abc123    ││
│ │ 1    │ ░░░░░░░░░░░░░░░░░░  5%  │  1G/16G  │ 45°C   │ free (30s)    ││
│ │ 2    │ ████████████████░░ 79%  │ 13G/16G  │ 69°C   │ job_abc123    ││
│ │ 3    │ ░░░░░░░░░░░░░░░░░░  3%  │  1G/16G  │ 43°C   │ free (45s)    ││
│ └──────┴─────────────────────────┴──────────┴────────┴───────────────┘│
│                                                                        │
│ gpu2 - 8 GPUs (8 free, 0 in use)                                      │
│ ┌──────┬─────────────────────────┬──────────┬────────┬───────────────┐│
│ │ GPU  │ Utilization             │ Memory   │ Temp   │ Job           ││
│ ├──────┼─────────────────────────┼──────────┼────────┼───────────────┤│
│ │ 0    │ ░░░░░░░░░░░░░░░░░░  3%  │  1G/32G  │ 38°C   │ free (120s)   ││
│ │ 1    │ ░░░░░░░░░░░░░░░░░░  2%  │  1G/32G  │ 36°C   │ free (115s)   ││
│ │ ...                                                                 ││
│ └──────┴─────────────────────────┴──────────┴────────┴───────────────┘│
│                                                                        │
│ Note: "free (Xs)" shows how long GPU has been below threshold         │
└────────────────────────────────────────────────────────────────────────┘
```

**Search/Filter (press '/'):**
```
┌────────────────────────────────────────────────────────────────────────┐
│ Search: train█                                                         │
├────────────────────────────────────────────────────────────────────────┤
│ Results: 3 jobs matching "train"                                       │
│ ┌──────────────┬──────────────┬──────────┬──────┬──────┐              │
│ │ Job ID       │ Name         │ Status   │ Node │ GPUs │              │
│ ├──────────────┼──────────────┼──────────┼──────┼──────┤              │
│ │ job_abc123   │ train.py     │ running  │ gpu1 │ 2    │              │
│ │ job_ghi789   │ pretrain.py  │ running  │ gpu3 │ 4    │              │
│ │ job_xyz456   │ retrain.py   │ pending  │ -    │ 2    │              │
│ └──────────────┴──────────────┴──────────┴──────┴──────┘              │
│                                                                        │
│ [ESC] Clear search  [Enter] Select                                     │
└────────────────────────────────────────────────────────────────────────┘
```

**Auto-refresh**: The display refreshes every 2 seconds by default (configurable).

**Examples:**

```bash
# Launch interactive status monitor
scheduler status

# The TUI automatically finds the head node from:
# 1. Local head node if running on same machine
# 2. ~/.scheduler/config.yaml address setting
# 3. SCHEDULER_ADDRESS environment variable
```

**Exit Codes:**
- `0` - Normal exit (user quit)
- `3` - Cannot connect to head node

---

## Job Submission

### `scheduler submit`

Submit a new job to the scheduler.

**Usage:**
```bash
scheduler submit [OPTIONS] SCRIPT [-- SCRIPT_ARGS...]
```

**Positional Arguments:**

| Argument | Description |
|----------|-------------|
| `SCRIPT` | Path to the script to execute (Python, bash, etc.) |
| `SCRIPT_ARGS` | Arguments to pass to the script (after `--`) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--req` | string | `1` | Resource requirements (see format below) |
| `--depends-on` | list | none | Comma-separated list of job IDs this job depends on |
| `--name` | string | script name | Human-readable job name |
| `--priority` | int | `0` | Job priority (higher = more important) |
| `--env` | list | none | Environment variables (KEY=VALUE format, can be repeated) |
| `--working-dir` | path | current dir | Working directory for job execution |
| `--async` | flag | false | Submit and return immediately without waiting |
| `--log-to-driver` | flag | false | Stream logs to stdout in real-time |

**Resource Requirement Format (`--req`):**

The `--req` flag supports flexible resource specifications:

| Format | Meaning | Example |
|--------|---------|---------|
| `N` | N GPUs on any available node | `--req 2` |
| `node1:N` | N GPUs on node1 specifically | `--req gpu1:2` |
| `node1:N,node2:M` | N GPUs on node1 OR M GPUs on node2 | `--req gpu1:2,gpu2:4` |

**Examples:**

```bash
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

```

**Output:**
```
Job submitted successfully!
Job ID: job_abc123def456
Status: pending
Requirements: 2 GPUs on any node
View status: scheduler status (then press 'J' and search for job)
```

**Job ID Assignment:**
The command returns the job ID which can be captured:
```bash
JOB_ID=$(scheduler submit --req 2 --async train.py | grep "Job ID" | awk '{print $3}')
echo $JOB_ID  # job_abc123def456
```

---

## Job Management

### `scheduler jobs`

List jobs in non-interactive mode (use `scheduler status` for interactive TUI).

**Usage:**
```bash
scheduler jobs [OPTIONS] [JOB_ID...]
```

**Positional Arguments:**

| Argument | Description |
|----------|-------------|
| `JOB_ID` | Job ID(s) to query (if omitted, shows recent jobs) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format` | choice | `table` | Output format: table, json, yaml |
| `--filter` | choice | `all` | Filter: all, pending, running, completed, failed |
| `--limit` | int | `50` | Maximum number of jobs to show |

**Examples:**
```bash
# Show specific job status
scheduler jobs job_abc123

# Show all jobs
scheduler jobs

# Show all running jobs
scheduler jobs --filter running

# Show last 100 jobs as JSON
scheduler jobs --format json --limit 100
```

**Output (table format):**
```
JOB_ID          NAME              STATUS    NODE   GPUS  RUNTIME  SUBMITTED
job_abc123      train.py          running   gpu1   2     00:15:32 2025-10-21 10:30:00
job_def456      eval.py           pending   -      1     -        2025-10-21 10:35:00
job_ghi789      preprocess.py     completed gpu2   1     00:05:12 2025-10-21 10:20:00
```

---

### `scheduler logs`

View logs for a specific job.

**Usage:**
```bash
scheduler logs [OPTIONS] JOB_ID
```

**Positional Arguments:**

| Argument | Description |
|----------|-------------|
| `JOB_ID` | Job ID to view logs for |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--follow` / `-f` | flag | false | Follow log output (like tail -f) |
| `--lines` / `-n` | int | `100` | Number of lines to show (from end) |
| `--timestamps` | flag | false | Show timestamps for each line |
| `--stderr` | flag | false | Show stderr instead of stdout |
| `--both` | flag | false | Show both stdout and stderr |

**Examples:**
```bash
# View last 100 lines of job logs
scheduler logs job_abc123

# Follow logs in real-time
scheduler logs -f job_abc123

# View last 500 lines with timestamps
scheduler logs --lines 500 --timestamps job_abc123

# View stderr only
scheduler logs --stderr job_abc123

# View both stdout and stderr
scheduler logs --both job_abc123
```

---

### `scheduler cancel`

Cancel one or more pending or running jobs.

**Usage:**
```bash
scheduler cancel [OPTIONS] JOB_ID...
```

**Positional Arguments:**

| Argument | Description |
|----------|-------------|
| `JOB_ID` | Job ID(s) to cancel |

**Examples:**
```bash
# Cancel a specific job
scheduler cancel job_abc123

# Cancel multiple jobs
scheduler cancel job_abc123 job_def456 job_ghi789
```

---

## Configuration

### `scheduler config`

Manage scheduler configuration.

**Usage:**
```bash
scheduler config [OPTIONS] [COMMAND]
```

**Commands:**

| Command | Description |
|---------|-------------|
| `init` | Initialize configuration file |
| `show` | Show current configuration |
| `set KEY VALUE` | Set a configuration value |
| `get KEY` | Get a configuration value |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--config-file` | path | `~/.scheduler/config.yaml` | Path to configuration file |

**Examples:**
```bash
# Initialize default configuration
scheduler config init

# Show current configuration
scheduler config show

# Set head node address
scheduler config set address 192.168.1.100:8265

# Get a configuration value
scheduler config get address
```

**Configuration File Format (YAML):**
```yaml
# ~/.scheduler/config.yaml

# Head node address (for worker nodes and clients)
address: 192.168.1.100:8265

# Default node settings
node:
  temp_dir: ~/.scheduler/tmp
  log_dir: ~/.scheduler/logs
  gpu_poll_interval: 10
  gpu_util_threshold: 10
  gpu_mem_threshold: 10
  gpu_stable_time: 30
  job_startup_grace: 120

# Head node settings (only used if running as head)
head:
  port: 8265
  heartbeat_timeout: 60
  scheduling_interval: 5
  graceful_shutdown_timeout: 60

# Client defaults
client:
  default_req: "1"  # Default GPU requirement
```

---

## Environment Variables

Environment variables that affect scheduler behavior:

| Variable | Description | Default |
|----------|-------------|---------|
| `SCHEDULER_ADDRESS` | Head node address (host:port) | from config file |
| `SCHEDULER_CONFIG` | Path to config file | `~/.scheduler/config.yaml` |
| `SCHEDULER_LOG_LEVEL` | Global log level | `INFO` |
| `SCHEDULER_TEMP_DIR` | Temporary directory | `~/.scheduler/tmp` |

**Examples:**
```bash
# Override head node address
export SCHEDULER_ADDRESS=192.168.1.100:8265
scheduler submit --req 2 train.py

# Use custom config file
export SCHEDULER_CONFIG=/path/to/custom/config.yaml
scheduler status

# Enable debug logging
export SCHEDULER_LOG_LEVEL=DEBUG
scheduler start --address=head:8265
```

### Debug Logging

The scheduler provides extensive debug logging to help troubleshoot issues:

**Available Log Levels:**
- `DEBUG` - Detailed execution flow, GPU monitoring, scheduling decisions
- `INFO` - General operation status (default)
- `WARNING` - Non-critical issues
- `ERROR` - Critical errors

**Debug Information Includes:**
- GPU stability tracking and free GPU detection
- Job scheduling decisions and node selection
- Heartbeat and node registration events
- Job execution and completion status
- API request/response details

**Examples:**
```bash
# Enable debug logging for head node
SCHEDULER_LOG_LEVEL=DEBUG scheduler start --head

# Enable debug logging for worker node
SCHEDULER_LOG_LEVEL=DEBUG scheduler start --address=head:8265

# View debug logs
tail -f ~/.scheduler/logs/scheduler-head.log
tail -f ~/.scheduler/logs/scheduler-worker.log
```

**Debug Log Format:**
```
[2025-10-24 17:21:46.081945] Node worker1.get_free_gpus: checking 8 GPUs with thresholds util=10.0%, mem=10.0%, stable_time=2s
[2025-10-24 17:21:46.081945] GPU 1: util=0.0%, mem=1.4%, is_free=True, is_stable=True, stable_since=2025-10-24 17:21:33.113722, elapsed=12.97s
[2025-10-24 17:21:46.081945] GPU 1: ADDED to free GPUs
[2025-10-24 17:21:46.081945] Node worker1: FINAL free GPUs = [1, 2, 3, 4, 5, 6, 7]
```

---

## Common Workflows

### Initial Setup

```bash
# 1. Start head node on a central machine
scheduler start --head

# 2. Start worker nodes on each GPU machine
# On gpu1:
scheduler start --address=head-machine:8265 --node-name=gpu1

# On gpu2:
scheduler start --address=head-machine:8265 --node-name=gpu2

# 3. Verify cluster is running
scheduler status
```

### Running Nodes in Background

If you want nodes to run in the background without blocking your terminal:

```bash
# Using nohup
nohup scheduler start --head > scheduler.log 2>&1 &

# Or using screen
screen -S scheduler-head
scheduler start --head
# Press Ctrl+A, D to detach

# Or using tmux
tmux new -s scheduler-head
scheduler start --head
# Press Ctrl+B, D to detach
```

### Submit a Training Pipeline

```bash
# Stage 1: Preprocess data (1 GPU on any node)
JOB1=$(scheduler submit --req 1 --name "preprocess" --async preprocess.py | grep "Job ID" | awk '{print $3}')

# Stage 2: Train model (4 GPUs, depends on stage 1, prefer gpu1)
JOB2=$(scheduler submit --req gpu1:4,gpu2:4 \
                        --depends-on $JOB1 \
                        --name "train" \
                        --async \
                        train.py | grep "Job ID" | awk '{print $3}')

# Stage 3: Evaluate (1 GPU, depends on stage 2)
JOB3=$(scheduler submit --req 1 \
                        --depends-on $JOB2 \
                        --name "eval" \
                        --async \
                        eval.py | grep "Job ID" | awk '{print $3}')

# Monitor all stages interactively
scheduler status
# Press 'J' to view jobs, then '/' to search for your jobs
```

### Monitor System Status

```bash
# Interactive TUI (recommended)
scheduler status

# Non-interactive job listing
scheduler jobs --filter running

# Tail logs for a specific job
scheduler logs -f job_abc123
```

---

## Exit Codes

All commands return standard exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Command-line argument error |
| `3` | Connection error (cannot reach head node) |
| `4` | Job/node not found |
| `5` | Permission denied |
| `6` | Timeout |

---

## Python API

For programmatic integration, the scheduler provides a Python client library. This is the recommended way to interact with the scheduler from Python scripts and applications.

### Installation

```bash
pip install gpu-scheduler
```

### Quick Start

```python
from scheduler import SchedulerClient

# Connect to scheduler
client = SchedulerClient(address="head-node:8265")

# Submit job
job = client.submit_job(
    script="train.py",
    requirements="2",
    name="my-job"
)
print(f"Job {job.job_id} submitted")

# Monitor job
job = client.get_job(job.job_id)
print(f"Status: {job.status}")
```

### Complete API Documentation

See the [Python API section in README.md](README.md#python-api) for:
- Complete API reference for `SchedulerClient`
- All available methods (submit, list, cancel, logs, etc.)
- Exception handling
- Data models (Job, Node, GPU, etc.)
- Configuration options
- Usage examples (batch submission, monitoring, ML integration)

### Key Methods

- `submit_job()` - Submit a new job
- `list_jobs()` - List jobs with optional filtering
- `get_job()` - Get job details
- `cancel_job()` - Cancel a job
- `get_job_logs()` - Get job logs
- `stream_job_logs()` - Stream logs in real-time
- `list_nodes()` - List all nodes
- `get_node()` - Get node details
- `health_check()` - Check head node health

### Example: Submit and Monitor

```python
from scheduler import SchedulerClient, JobStatus
import time

client = SchedulerClient()

# Submit
job = client.submit_job("train.py", "4", name="training")

# Monitor
while True:
    job = client.get_job(job.job_id)
    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
        break
    print(f"Status: {job.status}, Node: {job.assigned_node}")
    time.sleep(5)

print(client.get_job_logs(job.job_id, lines=50))
```

---

## API Endpoint Reference (Advanced)

For direct HTTP API access:

**Base URL:** `http://<head-node-host>:<port>/api/v1`

### Job Endpoints

- `POST /jobs` - Submit a new job
  - Body: `{"script": "train.py", "requirements": "gpu1:2,gpu2:4", "name": "my-job"}`
- `GET /jobs` - List all jobs (with filters)
- `GET /jobs/{job_id}` - Get job details
- `DELETE /jobs/{job_id}` - Cancel a job
- `GET /jobs/{job_id}/logs` - Stream job logs

### Node Endpoints

- `POST /nodes/register` - Register a new node (worker only)
  - Body: `{"node_name": "gpu1", "num_gpus": 4}`
- `POST /nodes/{node_name}/heartbeat` - Send heartbeat (worker only)
  - Body: `{"gpu_stats": [{"gpu_id": 0, "util": 5, "mem_used": 1024, "mem_total": 16384, "temp": 45, "power": 50}]}`
- `GET /nodes` - List all nodes
- `GET /nodes/{node_name}` - Get node details

### Worker Endpoints

- `GET /workers/{node_name}/jobs/next` - Poll for next job assignment (worker only)
- `POST /workers/jobs/{job_id}/complete` - Mark job complete (worker only)
- `POST /workers/jobs/{job_id}/fail` - Mark job failed (worker only)

---

## Resource Requirement Specification Details

### Syntax Grammar

```
<req> ::= <simple> | <compound>
<simple> ::= <num_gpus> | <node_spec>
<compound> ::= <node_spec> "," <node_spec> [, ...]
<node_spec> ::= [<node_name> ":"] <num_gpus>
<num_gpus> ::= positive integer
<node_name> ::= alphanumeric string with hyphens/underscores
```

### Examples with Interpretation

| Requirement | Interpretation |
|-------------|----------------|
| `--req 1` | 1 GPU on any available node |
| `--req 4` | 4 GPUs on any available node |
| `--req gpu1:2` | 2 GPUs specifically on node "gpu1" |
| `--req gpu1:2,gpu2:2` | 2 GPUs on "gpu1" OR 2 GPUs on "gpu2" (scheduler picks first available) |
| `--req gpu1:4,gpu2:8,gpu3:4` | 4 GPUs on gpu1 OR 8 GPUs on gpu2 OR 4 GPUs on gpu3 |

### Scheduling Behavior

When multiple node options are specified (comma-separated), the scheduler:
1. Evaluates each option from left to right
2. Checks if the node exists, is connected, and has enough free GPUs
3. A GPU is considered "free" only if it has been below the utilization threshold for at least `gpu_stable_time` seconds
4. Selects the first option that satisfies all conditions
5. If no options are currently available, job remains pending until one becomes available
6. When a job is assigned to a node, that node enters a grace period (`job_startup_grace`) during which no new jobs will be scheduled

---

## Notes

1. **No Sudo Required**: All operations use user-space directories and ports >= 1024
2. **Job IDs**: All job IDs are in the format `job_<uuid>` (e.g., `job_abc123def456`)
3. **Node Names**: Node names must be unique and URL-safe (alphanumeric + hyphens/underscores)
4. **File Versioning**: Jobs create versioned copies of scripts automatically (e.g., `train.py.scheduler_job_abc123_a1b2c3d4.py`)
5. **GPU Allocation**: GPUs are allocated via `CUDA_VISIBLE_DEVICES` environment variable
6. **Logs**: All job logs are stored in `<log-dir>/<job-id>/` on the executing node
7. **Auto-detection**: Commands automatically find the head node from local instance, config file, or environment variable
8. **CUDA_VISIBLE_DEVICES Compliance**: Not all frameworks respect `CUDA_VISIBLE_DEVICES`. The scheduler cannot enforce this at the system level. Users should verify their code respects GPU assignments or manually configure GPU visibility in their scripts.

---

## Troubleshooting

### Node won't start
```bash
# Check if another scheduler instance is running
ps aux | grep scheduler

# Check network connectivity to head node
curl http://head-machine:8265/api/v1/health

# Try with explicit address
scheduler start --address=192.168.1.100:8265 --node-name=my-node
```

### Job stuck in pending
```bash
# Check cluster status interactively
scheduler status
# Press 'N' to see node details and GPU availability

# Check specific job requirements non-interactively
scheduler jobs job_abc123

# Check node GPU availability manually
ssh gpu1 "nvidia-smi"
```

### Cannot connect to head node
```bash
# Test connectivity
curl http://head-machine:8265/api/v1/health

# Check configuration
scheduler config get address

# Set address if not configured
scheduler config set address 192.168.1.100:8265
```

### Head node stopped unexpectedly
```bash
# Check logs
cat ~/.scheduler/logs/scheduler-head.log

# Restart head node
scheduler start --head

# All worker nodes should automatically reconnect
```

### Jobs not scheduling despite free GPUs
```bash
# Check if GPUs are stable (not in grace period)
scheduler status
# Press 'G' to see detailed GPU view with stability timers

# Check if node is in job startup grace period
# The status TUI shows this information

# Consider tuning parameters:
# - Decrease gpu_stable_time if too conservative
# - Decrease job_startup_grace if jobs initialize quickly
# - Decrease gpu_util_threshold for stricter detection
```

---

*This document will be updated as new features are added.*
