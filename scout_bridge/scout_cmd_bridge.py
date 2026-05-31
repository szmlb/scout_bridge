import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import roslibpy


class ScoutCmdBridge(Node):
    """Bridge ROS2 /scout/cmd_vel to Scout ROS1 /cmd_vel via rosbridge WebSocket.

    Scout's /cmd_vel has non-standard axis mapping:
      linear.x = strafe, linear.y = forward/back, angular.z = rotation
    This node remaps from standard ROS2 convention before publishing.
    """

    def __init__(self):
        super().__init__('scout_cmd_bridge')
        self.declare_parameter('scout_host', 'scout')
        self.declare_parameter('scout_port', 9090)
        self.declare_parameter('reconnect_interval', 5.0)

        self._host = self.get_parameter('scout_host').value
        self._port = self.get_parameter('scout_port').value
        reconnect_interval = self.get_parameter('reconnect_interval').value

        self._ros1_client = None
        self._ros1_topic = None
        self._lock = threading.Lock()

        self._sub = self.create_subscription(
            Twist,
            '/scout/cmd_vel',
            self._cmd_vel_callback,
            10,
        )

        self._connect()

        self._reconnect_timer = self.create_timer(
            reconnect_interval, self._check_connection
        )
        self.get_logger().info(
            f'scout_cmd_bridge started, connecting to {self._host}:{self._port}'
        )

    def _connect(self):
        with self._lock:
            if self._ros1_client is not None:
                try:
                    self._ros1_client.close()
                except Exception:
                    pass

            try:
                client = roslibpy.Ros(host=self._host, port=self._port)

                def on_ready():
                    self.get_logger().info(
                        f'Connected to rosbridge at {self._host}:{self._port}'
                    )

                client.on_ready(on_ready, run_in_thread=False)
                client.run()  # starts Twisted reactor in daemon thread (no signal handlers)

                self._ros1_client = client
                self._ros1_topic = roslibpy.Topic(
                    client, '/cmd_vel', 'geometry_msgs/Twist'
                )
            except Exception as e:
                self.get_logger().warn(f'Connection attempt failed: {e}')
                self._ros1_client = None
                self._ros1_topic = None

    def _check_connection(self):
        with self._lock:
            connected = (
                self._ros1_client is not None and self._ros1_client.is_connected
            )
        if not connected:
            self.get_logger().warn('rosbridge disconnected, attempting reconnect...')
            self._connect()

    def _cmd_vel_callback(self, msg: Twist):
        with self._lock:
            if self._ros1_topic is None or not self._ros1_client.is_connected:
                self.get_logger().warn('Not connected to rosbridge, dropping cmd_vel')
                return
            topic = self._ros1_topic

        # Axis remapping from ROS2 standard to Scout convention:
        #   ROS2 linear.x (forward) → Scout linear.y (forward)
        #   ROS2 linear.y (strafe)  → Scout linear.x (strafe)
        #   ROS2 angular.z          → Scout angular.z (unchanged)
        ros1_msg = {
            'linear':  {'x': msg.linear.y,  'y': msg.linear.x,  'z': 0.0},
            'angular': {'x': 0.0,           'y': 0.0,           'z': msg.angular.z},
        }
        try:
            topic.publish(roslibpy.Message(ros1_msg))
        except Exception as e:
            self.get_logger().warn(f'Failed to publish to rosbridge: {e}')

    def destroy_node(self):
        with self._lock:
            if self._ros1_client is not None:
                try:
                    self._ros1_client.close()
                except Exception:
                    pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ScoutCmdBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
