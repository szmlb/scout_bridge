from setuptools import find_packages, setup

package_name = 'scout_bridge'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/scout_bridge.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='szmlb',
    maintainer_email='szmlb.robotics@gmail.com',
    description='ROS2 bridge for Moorebot Scout via rosbridge WebSocket',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'scout_cmd_bridge = scout_bridge.scout_cmd_bridge:main',
        ],
    },
)
