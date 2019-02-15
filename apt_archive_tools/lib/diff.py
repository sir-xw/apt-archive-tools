# coding:utf-8

from __future__ import print_function

'''
Created on 2017-2-22

@author: xiewei
'''

cmd_doc = """
Usage: archive_man diff [-t <type>] [-f|-c] <source1> <source2>
       archive_man diff -m <archive1> <archive2>

source1: 第一个对比目录，里面应该存在Release文件
source2: 第二个对比目录，里面应该存在Release文件
archive1: 第一个对比仓库，里面应该存在dists子目录
archive2: 第二个对比仓库，里面应该存在dists子目录

options:
   -t, --type=<type>        对比类型：source或binary [default: source]
   -f, --file               输出文件名而不是版本号
   -c, --compare            比较版本号大小
   -m, --md5                比较两个仓库中同名文件的md5值
   -h, --help               show this help

"""

import os
import glob
from ..contrib import docopt
from . import utils

import logging

logger = logging.getLogger('archive_man')


def diff(dist1, dist2, method='source', listfile=False, compare=False):
    release1 = utils.Release.parse(os.path.join(dist1, 'Release'))
    release2 = utils.Release.parse(os.path.join(dist2, 'Release'))

    logger.info('开始分析软件包列表')

    versions1 = {}
    versions2 = {}

    for vs, r in (versions1, release1), (versions2, release2):
        # 同一个系列中先确定最高版本
        if method == 'source':
            all_packages = r.all_sources.values()
        else:
            all_packages = r.all_packages.values()

        for packages in all_packages:
            for pkg in packages:
                pkgname = pkg.name + ', ' + pkg.arch
                old_version = vs.get(pkgname, '')
                if pkg <= old_version:
                    continue
                vs[pkgname] = pkg

    logger.info('开始比较')
    # 输出对比结果
    for pkgname in set(versions1.keys()) - set(versions2.keys()):
        if listfile:
            print(pkgname, ',', filepath(versions1[pkgname]))
        else:
            print(pkgname, ',', versions1[pkgname].version)
    for pkgname in set(versions1.keys()) & set(versions2.keys()):
        cmp_res = versions1[pkgname].__cmp__(versions2[pkgname])
        if compare:
            if cmp_res == 0:
                cmp_char = '='
            elif cmp_res < 0:
                cmp_char = '<'
            else:
                cmp_char = '>'
            print(pkgname, ',', versions1[pkgname].version, ',',
                  cmp_char, ',', versions2[pkgname].version)
        elif cmp_res == 0:
            continue
        elif listfile:
            print(pkgname, ',', filepath(versions1[pkgname]), ',', filepath(versions2[pkgname]))
        else:
            print(pkgname, ', ,', versions1[pkgname].version, ',', versions2[pkgname].version)
    for pkgname in set(versions2.keys()) - set(versions1.keys()):
        if listfile:
            print(pkgname, ', ,', filepath(versions2[pkgname]))
        else:
            print(pkgname, ', , ,', versions2[pkgname].version)

    logger.info('比较完成')
    return 0


def diff_md5(archive1, archive2):
    hash_table1 = {}
    hash_table2 = {}

    for topdir, hash_table in ((archive1, hash_table1), (archive2, hash_table2)):
        index_dir = os.path.join(topdir, 'dists')
        if not os.path.isdir(index_dir):
            logger.error('%s 不是一个软件源目录', topdir)
            return 1
        for release_file in glob.glob(os.path.join(index_dir, '*', 'Release')):
            release = utils.Release.parse(release_file)
            for packages in release.all_packages.values() + release.all_sources.values():
                for package in packages:
                    if isinstance(package, utils.Source):
                        for md5, _size, filepath in package.fileinfos:
                            hash_table[filepath] = md5
                    else:
                        hash_table[package.filename] = package.md5sum
    # compare
    for fn in set(hash_table1.keys()) & set(hash_table2.keys()):
        md5_1 = hash_table1[fn]
        md5_2 = hash_table2[fn]
        if md5_1 != md5_2:
            print(fn, ',', md5_1, ',', md5_2)

    return 0


def filepath(package):
    try:
        return package.filename
    except:
        return '|'.join(package.files)


def main(argv=None):
    """
    compare the package list of two dists
    """
    args = docopt.docopt(cmd_doc, argv, help=True, version='1.0')

    if args['--md5']:
        return diff_md5(args['<archive1>'], args['<archive2>'])
    else:
        return diff(dist1=args['<source1>'],
                    dist2=args['<source2>'],
                    method=args['--type'],
                    listfile=args['--file'],
                    compare=args['--compare'],
                    )
