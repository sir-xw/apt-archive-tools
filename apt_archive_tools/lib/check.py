# coding:utf-8

from __future__ import print_function

'''
Created on 2018-12-05

@author: xiewei
'''

cmd_doc = """
检查dists索引里的软件包和pool中的deb文件列表是否一致，输出多余或缺失的deb包路径
Usage: archive_man check <dir> [-s <suite>] [-m|--size]

dir: 软件源目录，里面应该有dists和软件包目录（通常取名为pool）

options:
   -s, --suite=<suite>         仅仅检查指定系列的索引中缺失的文件（未实装）
   -m, --md5                   检查仓库文件的md5是否与索引文件中一致
                               不一致的以前缀 ! 输出
   --size                      检查size而不是md5，节省时间
   -h, --help                  show this help

"""

import os
from ..contrib import docopt
from . import utils

import logging

logger = logging.getLogger('archive_man')


def check(topdir, suite=None, check_md5=False, check_size=False):
    # TODO: check single suite
    index_dir = os.path.join(topdir, 'dists')
    if not os.path.isdir(index_dir):
        logger.error('%s 不是一个软件源目录', topdir)
        return False

    # find all Packages and Sources
    P_files = set()
    S_files = set()
    pool_files = set()
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
            filelist.add(os.path.join(folder, subfile))

    hash_table = {}
    size_table = {}
    keep_list = set()
    for filepath in P_files:
        for package in utils.Packages.parse(filepath):
            package_abs_path = os.path.join(topdir, package.filename)
            hash_table[package_abs_path] = package.md5sum
            size_table[package_abs_path] = package.size
            keep_list.add(package_abs_path)
            if os.path.islink(package_abs_path):
                # 链接目标保留
                keep_list.add(os.path.realpath(package_abs_path))
    for filepath in S_files:
        for source in utils.Sources.parse(filepath):
            for md5sum, size, filepath in source.fileinfos:
                source_abs_path = os.path.join(topdir, filepath)
                hash_table[source_abs_path] = md5sum
                size_table[source_abs_path] = size
                keep_list.add(source_abs_path)
                if os.path.islink(source_abs_path):
                    # 链接目标保留
                    keep_list.add(os.path.realpath(source_abs_path))

    # 对比
    for filepath in pool_files - keep_list:
        print('+', filepath)

    for filepath in keep_list - pool_files:
        print('-', filepath)

    if check_md5:
        for filepath, md5sum in hash_table.items():
            if not os.path.exists(filepath):
                continue
            if utils.file_hash(filepath) != md5sum:
                print('!', filepath)

    if check_size:
        for filepath, size in size_table.items():
            if filepath not in set(pool_files):
                continue
            if os.stat(filepath).st_size != size:
                print('!', filepath)

    logger.info('检查完成')
    return True


def main(argv=None):
    """
    check missing or unnecessary debian packages in archive
    """
    args = docopt.docopt(cmd_doc, argv, help=True, version='1.0')

    check(topdir=os.path.abspath(args['<dir>']),
          suite=args['--suite'],
          check_md5=args['--md5'],
          check_size=args['--size']
          )
    return 0
