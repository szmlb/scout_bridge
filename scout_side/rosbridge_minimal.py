#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Minimal rosbridge WebSocket server (rosbridge protocol v2.0).

Implements only the ops roslibpy uses to publish to Scout ROS1 topics:
  advertise, publish, unadvertise

Requires:
  - rospy (ROS Melodic, Python 2.7)
  - tornado  (pip2 install tornado)

Usage:
  python2 rosbridge_minimal.py [port]   # default port: 9090
"""
from __future__ import print_function
import json
import sys
import threading

import rospy
from geometry_msgs.msg import Twist
from tornado import ioloop
from tornado.websocket import WebSocketHandler
from tornado.web import Application


_publishers = {}
_pub_lock = threading.Lock()


def get_publisher(topic):
    with _pub_lock:
        if topic not in _publishers:
            if topic == '/cmd_vel':
                _publishers[topic] = rospy.Publisher(topic, Twist, queue_size=10)
            else:
                return None
        return _publishers[topic]


def make_twist(msg_dict):
    t = Twist()
    linear = msg_dict.get('linear', {})
    angular = msg_dict.get('angular', {})
    t.linear.x = float(linear.get('x', 0.0))
    t.linear.y = float(linear.get('y', 0.0))
    t.linear.z = float(linear.get('z', 0.0))
    t.angular.x = float(angular.get('x', 0.0))
    t.angular.y = float(angular.get('y', 0.0))
    t.angular.z = float(angular.get('z', 0.0))
    return t


class RosbridgeHandler(WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        rospy.loginfo('rosbridge: client connected from %s', self.request.remote_ip)

    def on_message(self, raw):
        try:
            msg = json.loads(raw)
        except ValueError:
            rospy.logwarn('rosbridge: invalid JSON, ignoring')
            return

        op = msg.get('op', '')

        if op == 'advertise':
            rospy.loginfo('rosbridge: advertise %s', msg.get('topic', ''))

        elif op == 'publish':
            topic = msg.get('topic', '')
            payload = msg.get('msg', {})
            pub = get_publisher(topic)
            if pub is None:
                rospy.logwarn('rosbridge: unsupported topic %s', topic)
                return
            try:
                pub.publish(make_twist(payload))
            except Exception as e:
                rospy.logerr('rosbridge: publish error on %s: %s', topic, e)

        elif op in ('unadvertise', 'subscribe', 'unsubscribe'):
            pass  # no-op for this minimal implementation

        else:
            rospy.logdebug('rosbridge: unhandled op=%s', op)

    def on_close(self):
        rospy.loginfo('rosbridge: client disconnected')


def ros_spin_thread():
    rospy.spin()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090

    rospy.init_node('rosbridge_websocket', anonymous=False)
    rospy.loginfo('rosbridge minimal server starting on port %d', port)

    spin_t = threading.Thread(target=ros_spin_thread)
    spin_t.daemon = True
    spin_t.start()

    app = Application([(r'/.*', RosbridgeHandler)])
    app.listen(port, address='0.0.0.0')
    rospy.loginfo('rosbridge WebSocket ready on 0.0.0.0:%d', port)
    ioloop.IOLoop.current().start()
