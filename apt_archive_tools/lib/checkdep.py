# coding:utf-8

'''
Created on 2017-03-24

@author: xiewei
'''

cmd_doc = """
检查软件源中是否存在依赖未满足的包
Usage: archive_man checkdep <suite> [-e <dependency_suite>...] [--ignore-noexist] [--ge-only]

suite: 软件源索引目录，里面应该有Release文件

options:
   --ignore-noexist   忽略未找到的依赖包,只显示版本号不满足的
   --ge-only          只对比要求>=的依赖，因为编译环境错误而导致的依赖偏差应该都是这种形式
   -e,--extra=<dependency_suite>  添加额外的源用于查找依赖

"""

import os
from ..contrib import docopt
from . import utils

import logging

logger = logging.getLogger('archive_man')


class DependMatch(Exception):
    pass


def checkdep(topdir, extra, ignore_noexist=False, ge_only=False):
    """
    查找依赖未满足的包
    """
    pkg_in_archive = {}
    release = utils.Release.parse(os.path.join(topdir, 'Release'))
    extra_releases = [utils.Release.parse(
        os.path.join(extradir, 'Release')) for extradir in extra]
    # find all Packages

    for r in [release] + extra_releases:
        for packages in r.all_packages.values():
            for pkg in packages:
                # package
                if pkg.name not in pkg_in_archive:
                    pkg_in_archive[pkg.name] = [pkg]
                else:
                    pkg_in_archive[pkg.name].append(pkg)
                # provides
                for provide in pkg.provides:
                    if provide not in pkg_in_archive:
                        pkg_in_archive[provide] = [pkg]
                    else:
                        pkg_in_archive[provide].append(pkg)

    # checkdep
    for packages in release.all_packages.values():
        for pkg in packages:
            for dep_group in pkg.dependencies:
                if not dep_group:
                    continue

                if ignore_noexist and True not in [pkg_in_archive.has_key(p[0].split(':')[0]) for p in dep_group]:
                    continue

                if ge_only and '>=' not in [dep[1] for dep in dep_group]:
                    continue

                try:
                    for depon, rel, version in dep_group:
                        depon_name = depon.split(':')[0]
                        deppkgs = pkg_in_archive.get(depon_name, [])
                        if not rel and deppkgs:
                            raise DependMatch()
                        else:
                            for deppkg in deppkgs:
                                if rel == '>=':
                                    ok = deppkg.binary_version >= version
                                elif rel == '<=':
                                    ok = deppkg.binary_version <= version
                                elif rel == '>=':
                                    ok = deppkg.binary_version >= version
                                elif rel in ['==', '=']:
                                    ok = deppkg.binary_version == version
                                elif rel in ['>', '>>']:
                                    ok = deppkg.binary_version > version
                                elif rel in ['<', '<<']:
                                    ok = deppkg.binary_version < version
                                else:
                                    raise Exception(
                                        'unknown relation: %s' % rel)
                                if ok:
                                    raise DependMatch()
                except DependMatch:
                    continue
                logger.error('%s:%s(%s) [source:%s] 有未满足的依赖:%s' %
                             (pkg.name, pkg.arch, pkg.version, pkg.source, dep_group))
    return True


def main(argv=None):
    """
    check dependencies of packages in an archive
    """
    args = docopt.docopt(cmd_doc, argv, help=True, version='1.0')
    checkdep(args['<suite>'],
             args['--extra'],
             args['--ignore-noexist'],
             args['--ge-only']
             )
    return 0
