#!/usr/bin/python
# encoding: utf-8
'''
archive_man -- apt archive manage tool

archive_man is a manage tool of APT software archives

@author:     Xie Wei
        
@copyright:  2016 KylinOS. All rights reserved.
        
@license:    GPL

@contact:    xiewei@kylinos.cn
@deffield    updated: Updated
'''

from __future__ import print_function
import os
import sys
from .contrib import docopt

__all__ = []

try:
    __version__ = open(os.path.join(os.path.dirname(__file__),
                                    '../VERSION')
                       ).read().strip()
    DEVELOP = True
except Exception:
    import pkg_resources
    __version__ = pkg_resources.get_distribution('apt-archive-tools').version
    DEVELOP = False
__date__ = '2016-06-14'
__updated__ = '2019-02-15'


def main():
    """cmd line entry"""

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__

    cmd_doc = """
Usage: %(prog)s [--help] [--quiet] <command> [<args>...]

options:
   -h, --help   Show this screen and exit.
   -q, --quiet  Do not show debug message.
Command list:
"""
    commands = {}
    if DEVELOP:
        import pkgutil
        import importlib
        from . import lib

        for _finder, name, _ispkg in pkgutil.iter_modules(lib.__path__, lib.__name__ + '.'):
            module = importlib.import_module(name)
            if hasattr(module, 'main'):
                if hasattr(module, 'command'):
                    command = module.command
                else:
                    command = name.split('.')[-1]
                commands[command] = module.main
    else:
        for entry_point in pkg_resources.iter_entry_points('apt_archive_tools.commands'):
            commands[entry_point.name] = entry_point.load()

    for c, f in commands.items():
        cmd_doc = cmd_doc + '   ' + c + '\n\t' + \
            (f.__doc__ or 'No description').strip() + '\n'

    cmd_doc += "\nSee '%(prog)s <command> --help' for more information on a specific command.\n"

    args = docopt.docopt(cmd_doc % {'prog': program_name},
                         help=True,
                         version=program_version,
                         options_first=True
                         )
    if args['--quiet']:
        from .lib import logger, logging
        logger.setLevel(logging.INFO)

    command = args['<command>']

    if command not in commands:
        print("%r is not a valid command. See '%s --help'." %
              (command, program_name))
        sys.exit(1)
    sys.exit(commands[command]([command] + args['<args>']))
