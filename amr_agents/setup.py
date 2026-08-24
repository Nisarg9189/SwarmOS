from setuptools import setup, find_packages

setup(
    name='amr_agents',
    version='0.1.0',
    packages=find_packages(exclude=['tests']),
    py_modules=['agent', 'task_dispatcher'],
    install_requires=[
        'rclpy',
        'numpy',
        'scipy',
    ],
    author='SwarmOS Developer',
    author_email='developer@swarmos.dev',
    description='SwarmOS coordination agents',
    license='Apache-2.0',
)
