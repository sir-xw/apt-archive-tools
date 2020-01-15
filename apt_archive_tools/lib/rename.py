# coding:utf-8

'''
Created on 2019-01-22

@author: xiewei
'''

cmd_doc = """
修改软件源索引中的软件包路径，注意：默认不会移动对应路径的文件；源码文件重命名的操作有点复杂，暂不支持。
Usage: archive_man rename <dir> <origin> <new> [-f]
       archive_man rename <dir> --list=<file> [-f]

dir:     软件源目录，里面应该有dists和软件包目录（通常取名为pool）
origin:  需要修改的路径
new:     修改后的路径

options:
   -f, --file                  also rename the real file
   -l, --list=<file>           read list of files to rename from a file
                               the file content like:
                                  origin1,new1
                                  origin2,new2
   -h, --help                  show this help

"""

import os
import glob
import re
from ..contrib import docopt
from . import utils

import logging

logger = logging.getLogger('archive_man')


def rename(topdir, pairs, file=False):
    index_dir = os.path.join(topdir, 'dists')
    if not os.path.isdir(index_dir):
        logger.error('%s 不是一个软件源目录', topdir)
        return 1

    # parse package index
    for release_file in glob.glob(os.path.join(index_dir, '*', 'Release')):
        release = utils.Release.parse(release_file)
        release_changed = False
        for packages in release.all_packages.values():
            changed = False
            for package in packages:
                fn = package.filename
                prefix_expr = r'(Filename: )'

                if fn in pairs:
                    changed = True
                    logger.debug('Found %s in %s', fn, packages.filepath)
                    new_fn = pairs[fn]
                    # change package info
                    package.text, match_n = re.subn(r'^' + prefix_expr + re.escape(fn) + '$',
                                                    r'\g<1>' + new_fn,
                                                    package.text,
                                                    flags=re.M)
                    if match_n < 0:
                        logger.error('replace action not match any result')
                        return 1
                    if file:
                        logger.debug('rename file')
                        old = os.path.join(topdir, fn)
                        new = os.path.join(topdir, new_fn)

                        if os.path.exists(new):
                            logger.debug(
                                'new path already exists, maybe renamed before')
                            continue

                        new_dir = os.path.dirname(new)
                        if not os.path.exists(new_dir):
                            os.makedirs(new_dir)

                        if os.path.islink(old):
                            # 从链接目标复制
                            os.system('cp "%s" "%s"' % (old, new))
                        else:
                            # 重命名
                            os.rename(old, new)

            if changed:
                logger.debug('Rewriting: %s', packages.filepath)
                packages.write()
                release_changed = True

        # update Release
        if release_changed:
            logger.debug('Rewriting Release file: %s', release_file)
            release.write()
    return 0


def main(argv=None):
    """
    change filename of package in the archive indexes
    """
    args = docopt.docopt(cmd_doc, argv, help=True, version='1.0')

    name_pairs = {}

    if args['--list']:
        logger.info('processing name list...')

        with open(args['--list']) as f:
            for line in f.readlines():
                try:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    a, b = stripped.split(',')
                    name_pairs[a.strip()] = b.strip()
                except:
                    logger.warning(
                        'Unable to parse filename pair from: %s', line)
                    pass

    else:
        name_pairs = {args['<origin>']: args['<new>']}

    return rename(os.path.abspath(args['<dir>']),
                  name_pairs,
                  file=args['--file']
                  )
