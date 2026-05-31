#!/bin/bash
# Startup script for rosbridge_minimal.py on Moorebot Scout (Debian 9, ROS Melodic).
# Waits for rosmaster (started by roller_eye.service) before launching the bridge.

source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://localhost:11311
export PYTHONPATH=/opt/ros/melodic/lib/python2.7/dist-packages:$PYTHONPATH

RETRIES=0
while ! pgrep -x "rosmaster" > /dev/null && [ $RETRIES -lt 10 ]; do
    sleep 2
    RETRIES=$((RETRIES + 1))
done

if ! pgrep -x "rosmaster" > /dev/null; then
    echo "rosmaster not found after waiting, starting roscore..."
    roscore &
    sleep 4
fi

exec python2 /opt/ros_launch/rosbridge_minimal.py 9090
