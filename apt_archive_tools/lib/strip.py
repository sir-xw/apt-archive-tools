# coding:utf-8

'''
Created on 2017-03-24

@author: xiewei
'''

cmd_doc = """
从软件源中删除已经不在dists索引里的包，减少其占用空间
Usage: archive_man strip <dir> [-b <backupdir>] [-d] [-i]

dir: 软件源目录，里面应该有dists和软件包目录（通常取名为pool）

options:
   -b, --backup=<backupdir>    多余的包不会被删除，而是移动到指定的备份目录中
   -d, --dry                   提示哪些文件会被删除，但并不执行
   -h, --help                  show this help
   -i, --index                 双向删除：同时会将已经不存在于pool中的包从索引中删除

"""

import os
import glob
from ..contrib import docopt
from . import utils

import logging

logger = logging.getLogger('archive_man')


def strip(topdir, backup, index, dryrun=False):
    """
    从软件源中删除已经不在dists索引里的包
    """
    index_dir = os.path.join(topdir, 'dists')
    if not os.path.isdir(index_dir):
        logger.error('%s 不是一个软件源目录', topdir)
        return 1

    if backup and not os.path.exists(backup):
        os.makedirs(backup)

    # find all Packages and Sources
    pool_files = set()
    keep_list = set()

    logger.debug('Collecting files')
    for folder, _, subfiles in os.walk(topdir):
        for subfile in subfiles:
            if folder.startswith(index_dir):
                continue
            else:
                pool_files.add(os.path.join(folder, subfile))

    # parse package index
    for release_file in glob.glob(os.path.join(index_dir, '*', 'Release')):
        release = utils.Release.parse(release_file)
        release_changed = False
        for packages in release.all_packages.values() + release.all_sources.values():
            new = utils.Packages(packages.filepath)
            changed = False
            for package in packages:
                if isinstance(package, utils.Source):
                    file_list = package.files
                else:
                    file_list = [package.filename]
                for filename in file_list:
                    package_abs_path = os.path.join(topdir, filename)
                    if index:
                        if package_abs_path in pool_files:
                            new[package.name] = package
                        else:
                            logger.debug('Missing file: %s', package_abs_path)
                            logger.debug('Remove %s from %s',
                                         package.name, packages.filepath)
                            changed = True
                            break
                    keep_list.add(package_abs_path)
                    if os.path.islink(package_abs_path):
                        # 链接目标保留
                        keep_list.add(os.path.realpath(package_abs_path))

            if index and changed:
                if dryrun:
                    logger.debug(
                        'Index file need to rewrite: %s', new.filepath)
                else:
                    logger.debug('Rewriting: %s', new.filepath)
                    new.write()
                    release_changed = True

    # update Release
    if release_changed:
        logger.debug('Rewriting Release file: %s', release_file)
        release.write()

    # 开始删除或移动
    for filepath in pool_files - keep_list:
        if dryrun:
            logger.debug('Find an unnecessary file: %s', filepath)
        elif backup:
            old_dir, _ = os.path.split(filepath)
            back_dir = backup + old_dir.replace(topdir, '', 1)
            if not os.path.exists(back_dir):
                os.makedirs(back_dir)
            cmd = 'mv "%s" "%s"' % (filepath, back_dir)
            logger.debug('Excecuting: %s', cmd)
            assert os.system(cmd) == 0
        else:
            logger.debug('Removing: %s', filepath)
            os.remove(filepath)

    if dryrun:
        logger.info('测试模式完成，没有改动任何文件')
    else:
        logger.info('裁剪完成')
    return 0


def main(argv=None):
    """
    remove unnecessary files from pool/ if local archive
    """
    args = docopt.docopt(cmd_doc, argv, help=True, version='1.0')

    backup = args['--backup']
    if not backup:
        backupdir = None
    else:
        backupdir = os.path.abspath(backup)

    return strip(topdir=os.path.abspath(args['<dir>']),
          backup=backupdir,
          index=args['--index'],
          dryrun=args['--dry']
          )
