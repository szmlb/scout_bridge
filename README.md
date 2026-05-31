# scout_bridge

ROS 2 package that bridges the [Moorebot Scout](https://www.moorebot.com/) home surveillance robot into a ROS 2 Jazzy environment via a WebSocket connection.

The Scout runs ROS 1 (Melodic-equivalent) internally on arm64/Debian 9. This package connects to a lightweight rosbridge WebSocket server running on the Scout and forwards velocity commands from ROS 2 topics, applying the axis remapping that Scout's firmware requires.

## Architecture

```
[Remote PC / ROS 2 Jazzy]
  ros2 topic pub /scout/cmd_vel geometry_msgs/Twist
        │
  scout_cmd_bridge node
  (roslibpy WebSocket client, axis remapping)
        │  WebSocket  port 9090
        ▼
[Moorebot Scout: aarch64, Debian 9, ROS 1]
  rosbridge_minimal.py  (tornado WebSocket server)
        │  rospy.Publisher
        ▼
  /cmd_vel  →  /MotorNode  →  motors
```

## Scout Device Specs

| Item | Value |
|---|---|
| Architecture | aarch64 (arm64) |
| OS | Debian GNU/Linux 9 (stretch) |
| Internal ROS | ROS 1 Melodic-equivalent |
| SSH user | `root` |

## Axis Remapping

Scout's `/cmd_vel` uses a non-standard axis convention. This package maps from ROS 2 standard before publishing:

| ROS 2 input (standard) | Scout `/cmd_vel` | Meaning |
|---|---|---|
| `linear.x` | `linear.y` | Forward / backward |
| `linear.y` | `linear.x` | Lateral (strafe) |
| `angular.z` | `angular.z` | Rotation (unchanged) |

---

## Part 1 — Scout-side Setup

These steps are performed **once on the Scout robot** over SSH. The rosbridge server runs as a systemd service and starts automatically on boot.

### Prerequisites

Scout must be accessible via SSH. See your network setup (Tailscale or LAN) for the hostname or IP.

```bash
ssh root@<scout-host>
```

### 1-1. Install pip for Python 2

Scout's Debian 9 apt repos are EOL. Install pip2 manually:

```bash
curl -s https://bootstrap.pypa.io/pip/2.7/get-pip.py -o /tmp/get-pip.py
python2 /tmp/get-pip.py
```

### 1-2. Install tornado

`ros-melodic-rosbridge-suite` cannot be installed via apt on this system due to missing Python 2 C-extension dependencies and no compiler. Instead, install tornado (pure Python WebSocket server) via pip2:

```bash
pip2 install tornado
```

Verify:

```bash
python2 -c "import tornado; print(tornado.version)"
```

### 1-3. Deploy the rosbridge server script

Copy `scout_side/rosbridge_minimal.py` from this repository to the Scout:

```bash
scp scout_side/rosbridge_minimal.py root@<scout-host>:/opt/ros_launch/rosbridge_minimal.py
chmod +x /opt/ros_launch/rosbridge_minimal.py
```

This script implements the minimum rosbridge v2 protocol needed to receive `publish` commands for `/cmd_vel`. It uses tornado for WebSocket and rospy to publish into Scout's ROS 1 master.

### 1-4. Deploy the startup script

```bash
scp scout_side/start_rosbridge.sh root@<scout-host>:/opt/ros_launch/start_rosbridge.sh
chmod +x /opt/ros_launch/start_rosbridge.sh
```

`start_rosbridge.sh` waits for rosmaster (started by Scout's own `roller_eye.service`) before launching the bridge.

### 1-5. Install the systemd service

```bash
scp scout_side/rosbridge.service root@<scout-host>:/etc/systemd/system/rosbridge.service
ssh root@<scout-host> "systemctl daemon-reload && systemctl enable rosbridge && systemctl start rosbridge"
```

The service starts after `roller_eye.service` (Scout's internal ROS bringup) on every boot.

### 1-6. Verify

From the Scout:

```bash
systemctl status rosbridge
ss -tlnp | grep 9090     # should show python2 listening
```

From the remote PC:

```bash
python3 -c "import socket; s=socket.create_connection(('<scout-host>', 9090), 5); print('OK'); s.close()"
```

---

## Part 2 — Remote PC Setup (ROS 2 side)

Tested on Ubuntu 24.04 with ROS 2 Jazzy. Scout must be reachable on port 9090 from the remote PC (Tailscale, LAN, or any routable network).

### 2-1. Install roslibpy

ROS 2 uses the system Python. Do **not** install roslibpy inside a conda environment.

```bash
# Install pip for system Python if not present
curl -s https://bootstrap.pypa.io/get-pip.py | python3 - --user --break-system-packages

# Install roslibpy
~/.local/bin/pip install roslibpy --break-system-packages
```

Verify it is importable by the system Python:

```bash
/usr/bin/python3 -c "import roslibpy; print(roslibpy.__version__)"
```

### 2-2. Build the package

```bash
cd ~/ros2_ws          # or wherever your ROS 2 workspace is
git clone https://github.com/szmlb/scout_bridge src/scout_bridge
source /opt/ros/jazzy/setup.bash
COLCON_PYTHON_EXECUTABLE=/usr/bin/python3 colcon build --packages-select scout_bridge
source install/setup.bash
```

> **Note:** If conda is active during build, the wrong Python may be picked up. Either deactivate conda first or set `COLCON_PYTHON_EXECUTABLE=/usr/bin/python3` as shown above.

---

## Usage

### Launch the bridge

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash

ros2 launch scout_bridge scout_bridge.launch.py
```

With a custom host (e.g., Tailscale IP instead of hostname):

```bash
ros2 launch scout_bridge scout_bridge.launch.py scout_host:=100.x.x.x
```

### Send a velocity command

In a second terminal (with the workspace sourced):

```bash
# Forward at 0.3 m/s (ROS 2 convention: linear.x = forward)
ros2 topic pub /scout/cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.3, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}'

# Stop
ros2 topic pub --once /scout/cmd_vel geometry_msgs/msg/Twist '{}'

# Rotate in place
ros2 topic pub /scout/cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.5}}'
```

### Node parameters

| Parameter | Default | Description |
|---|---|---|
| `scout_host` | `scout` | Hostname or IP of the Scout robot |
| `scout_port` | `9090` | rosbridge WebSocket port |
| `reconnect_interval` | `5.0` | Seconds between reconnection attempts |

### Direct node invocation (for debugging)

```bash
ros2 run scout_bridge scout_cmd_bridge --ros-args \
  -p scout_host:=<host> \
  -p scout_port:=9090
```

---

## Scout-side Files

The `scout_side/` directory contains the files deployed to the Scout. They are included here so the package is self-contained.

| File | Deployed to (on Scout) | Purpose |
|---|---|---|
| `scout_side/rosbridge_minimal.py` | `/opt/ros_launch/rosbridge_minimal.py` | WebSocket server (tornado + rospy) |
| `scout_side/start_rosbridge.sh` | `/opt/ros_launch/start_rosbridge.sh` | Startup script |
| `scout_side/rosbridge.service` | `/etc/systemd/system/rosbridge.service` | systemd unit file |

---

## Troubleshooting

| Symptom | Check |
|---|---|
| "Not connected to rosbridge" in node log | `python3 -c "import socket; socket.create_connection(('<host>', 9090), 5)"` |
| rosbridge port not open on Scout | `ssh root@<scout-host> "ss -tlnp | grep 9090"` |
| rosbridge service failed to start | `ssh root@<scout-host> "journalctl -u rosbridge -n 50"` |
| rosmaster not running on Scout | `ssh root@<scout-host> "pgrep -x rosmaster"` — restart `roller_eye.service` |
| `roslibpy` not found when building | Confirm `/usr/bin/python3 -c "import roslibpy"` works; do not use conda Python |
| Wrong axis response from Scout | Verify the axis mapping table above — Scout swaps `linear.x` and `linear.y` |

## Known Limitations

- Only `/cmd_vel` (`geometry_msgs/Twist`) is bridged. Camera stream (`/CoreNode/jpg`, custom `roller_eye/Frame` type) is not yet supported.
- The rosbridge implementation on Scout is minimal by design — it handles `advertise`, `publish`, and `unadvertise` ops only.
- `ros-melodic-rosbridge-suite` cannot be installed via apt on Scout's Debian 9 system (missing Python 2 C-extension dependencies, no compiler). The minimal tornado-based server in `scout_side/` is the workaround.
