# encoding: utf-8
'''
Created on 2016-6-23

@author: xiewei

把本地软件源再复制一份，pool目录里的包将会是源文件的硬链接，以节省空间

'''

from ..contrib import docopt
import os
import logging

logger = logging.getLogger('archive_man')

cmd_doc = """
Usage:
   archive_man local-copy <source-dir> <dest-dir>

Options:
   -h, --help   show this help
"""


def copy_archive(source, dest):
    if not os.path.isdir(os.path.join(source, 'pool')):
        logger.error(u'源目录不是一个软件源')
        return 1
    os.makedirs(dest, mode=0o755)
    # copy files
    for sub in os.listdir(source):
        result = os.system('cp -ar %s "%s" "%s"' % ('-l' if sub == 'pool' else '',
                                                    os.path.join(source, sub),
                                                    os.path.join(dest, sub)
                                                    ))
        if result == 0:
            logger.info(u'复制了 %s' % sub)
        else:
            logger.error(u'复制 %s 时出错' % sub)
            return result

    return 0


def main(argv=None):
    """
    just like cp, but files in pool/ will be a hardlink to source
    """
    args = docopt.docopt(cmd_doc, argv, help=True)
    return copy_archive(args['<source-dir>'], args['<dest-dir>'])
