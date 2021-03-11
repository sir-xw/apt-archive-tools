import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

with open('VERSION', 'r') as fh:
    version = fh.read().strip()

setuptools.setup(
    name='apt-archive-tools',
    version=version,
    author='Xie Wei',
    author_email='xw.master@live.cn',
    description='Apt archive toolkit',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/sir-xw/apt-archive-tools',
    packages=setuptools.find_packages(),
    license='GPLv2',
    classifiers=[
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: POSIX :: Linux',
    ],
    package_data={
        'apt_archive_tools.lib': ['default.conf']
    },
    entry_points={
        'console_scripts': [
            'archive-man = apt_archive_tools.archive_man:main'
        ],
        'apt_archive_tools.commands': [
            'key = apt_archive_tools.lib.key:main',
            'sign = apt_archive_tools.lib.sign:main',
            'copy = apt_archive_tools.lib.copy_archive:main',
            'local-copy = apt_archive_tools.lib.local_copy:main',
            'publish = apt_archive_tools.lib.publish:main',
            'merge = apt_archive_tools.lib.merge:main',
            'strip = apt_archive_tools.lib.strip:main',
            'diff = apt_archive_tools.lib.diff:main',
            'check = apt_archive_tools.lib.check:main',
            'checkdep = apt_archive_tools.lib.checkdep:main',
            'rename = apt_archive_tools.lib.rename:main'
        ]
    },
    install_requires=[
       "requests",
    ],
)
