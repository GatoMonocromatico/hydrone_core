import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'mission_bridge'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ivo',
    maintainer_email='ivoarpino2@gmail.com',
    description='ROS2 mission orchestration nodes (T10.2).',
    license='TODO',
    entry_points={
        'console_scripts': [
            'mission_state_publisher = mission_bridge.mission_state_publisher:main',
            'command_relay = mission_bridge.command_relay:main',
        ],
    },
)
