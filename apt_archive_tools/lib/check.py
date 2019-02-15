# coding:utf-8

from __future__ import print_function

'''
Created on 2018-12-05

@author: xiewei
'''

cmd_doc = """
检查dists索引里的软件包和pool中的deb文件列表是否一致，输出多余或缺失的deb包路径
Usage: archive_man check <dir>

dir: 软件源目录，里面应该有dists和软件包目录（通常取名为pool）

options:
   -h, --help                  show this help

"""

import os
from ..contrib import docopt
from . import utils

import logging

logger = logging.getLogger('archive_man')


def check(topdir):
    index_dir = os.path.join(topdir, 'dists')
    if not os.path.isdir(index_dir):
        logger.error('%s 不是一个软件源目录', topdir)
        return False

    # find all Packages and Sources
    P_files = []
    S_files = []
    pool_files = []
    for folder, _, subfiles in os.walk(topdir):
        for subfile in subfiles:
            if folder.startswith(index_dir):
                if subfile == 'Packages':
                    filelist = P_files
                elif subfile == 'Sources':
                    filelist = S_files
                else:
                    continue
            else:
                filelist = pool_files
            filelist.append(os.path.join(folder, subfile))

    keep_list = []
    for filepath in P_files:
        for package in utils.Packages.parse(filepath):
            package_abs_path = os.path.join(topdir, package.filename)
            keep_list.append(package_abs_path)
            if os.path.islink(package_abs_path):
                # 链接目标保留
                keep_list.append(os.path.realpath(package_abs_path))
    for filepath in S_files:
        for source in utils.Sources.parse(filepath):
            for filename in source.files:
                source_abs_path = os.path.join(topdir, filename)
                keep_list.append(source_abs_path)
                if os.path.islink(source_abs_path):
                    # 链接目标保留
                    keep_list.append(os.path.realpath(source_abs_path))

    # 对比
    for filepath in set(pool_files) - set(keep_list):
        print('+', filepath)

    for filepath in set(keep_list) - set(pool_files):
        print('-', filepath)

    logger.info('检查完成')
    return True


def main(argv=None):
    """
    check missing or unnecessary debian packages in archive
    """
    args = docopt.docopt(cmd_doc, argv, help=True, version='1.0')

    check(topdir=os.path.abspath(args['<dir>']))
    return 0
