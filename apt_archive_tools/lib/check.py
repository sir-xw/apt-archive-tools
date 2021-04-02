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
   -s, --suite=<suite>         仅仅检查指定系列的索引中缺失的文件
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
    index_dir = os.path.join(topdir, 'dists')
    if not os.path.isdir(index_dir):
        logger.error('%s 不是一个软件源目录', topdir)
        return False

    # find all Packages and Sources
    P_files = set()
    S_files = set()
    pool_files = set()
    symlinks = {}

    # all index files
    for folder, _, subfiles in os.walk(index_dir):
        if suite and folder.replace(index_dir+'/', '').split('/')[0] != suite:
            continue
        for subfile in subfiles:
            if subfile == 'Packages':
                P_files.add(os.path.join(folder, subfile))
            elif subfile == 'Sources':
                S_files.add(os.path.join(folder, subfile))
            else:
                continue

    # all pool files
    if not suite:
        for folder, _, subfiles in os.walk(topdir):
            if folder.startswith(index_dir):
                continue
            for subfile in subfiles:
                filepath = os.path.join(folder, subfile)
                pool_files.add(filepath)
                if os.path.islink(filepath):
                    symlinks[filepath] = os.path.realpath(filepath)

    hash_table = {}
    size_table = {}
    keep_list = set()
    for filepath in P_files:
        for package in utils.Packages.parse(filepath):
            package_abs_path = os.path.join(topdir, package.filename)
            if check_md5:
                # 检查不同索引文件中是否有同名文件不一致
                old_md5sum = hash_table.get(package_abs_path)
                if old_md5sum and package.md5sum != old_md5sum:
                    logger.error('hash of %s differ in index files', package_abs_path)
                hash_table[package_abs_path] = package.md5sum
            if check_size:
                # 检查不同索引文件中是否有同名文件不一致
                old_size = size_table.get(package_abs_path)
                if old_size and package.size != old_size:
                    logger.error('size of %s differ in index files', package_abs_path)
                size_table[package_abs_path] = package.size
            keep_list.add(package_abs_path)
            # 链接目标保留
            try:
                keep_list.add(symlinks[package_abs_path])
            except:
                pass
    for filepath in S_files:
        for source in utils.Sources.parse(filepath):
            for md5sum, size, filepath in source.fileinfos:
                source_abs_path = os.path.join(topdir, filepath)
                if check_md5:
                    old_md5sum = hash_table.get(source_abs_path)
                    if old_md5sum and md5sum != old_md5sum:
                        logger.error('hash of %s differ in index files', source_abs_path)
                    hash_table[source_abs_path] = md5sum
                if check_size:
                    old_size = size_table.get(source_abs_path)
                    if old_size and size != old_size:
                        logger.error('size of %s differ in index files', source_abs_path)
                    size_table[source_abs_path] = size
                keep_list.add(source_abs_path)
                # 链接目标保留
                try:
                    keep_list.add(symlinks[source_abs_path])
                except:
                    pass

    logger.info('Finished reading index')

    if suite:
        for filepath in keep_list:
            if os.path.exists(filepath):
                pool_files.add(filepath)
            else:
                print('-', filepath)
    else:
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
