# coding:utf8

'''
Created on 2017-2-22

@author: xiewei
'''

cmd_doc = """
Usage: archive_man merge [-d <topdir>] [-p <policy>] <source1> <source2>... -t <target> [-f] [-b] [-c]

source1: 第一个合并来源，应该是topdir中已存在的目录名
source2: 第二个合并来源，应该是topdir中已存在的目录名
...: 可提供更多合并来源

options:
   -d, --dir=<topdir>       dists目录的路径，默认为当前路径 [default: .]
   -p, --policy=<policy>    合并策略，默认取版本号最高 [default: version]
   -b, --binary             二进制包以包名而非source来判断是否同名包，这可以保留由不同版本source编译出的不同名称的包。
   -t, --target=<target>    合并后的系列名，注意如果是已存在的系列，里面的内容将会被替换（需要带 -f 选项）。
   -c, --contents           同时合并Contents文件
   -f, --force              如果目标系列已存在则会覆盖
   -h, --help               show this help

合并策略：
   对于相同源码名称的包，有三种合并策略：
   first：优先从参数中顺序靠前的系列中选取
   last：优先从参数中顺序靠后的系列中选取
   version：优先选源码版本号最高的

"""

import os
from ..contrib import docopt
from . import utils

import logging

logger = logging.getLogger('archive_man')


def merge(topdir, froms, target, policy='version', binary=False, force=False, with_contents=False):
    """
    合并多个系列中的Packages与Sources索引

    参数：
    topdir - 合并的系列应该属于同一个软件源，这里提供系列目录共同所在目录即 <xxx>/dists
    froms - 有序列表，内部元素是作为合并来源的系列名称
    target - 字符串，目标系列名称
    policy - 对于相同源码名称的包，有三种合并策略：
      first：从froms中顺序靠前的系列中选取
      last：从froms中顺序靠后的系列中选取
      version：选版本号高的
    """
    source_releases = [utils.Release.parse(os.path.join(
        topdir, series, 'Release')) for series in froms]
    # check target
    if os.path.exists(os.path.join(topdir, target)) and not force:
        logger.error('合并目标 "%s" 已存在' % target)
        return False

    def pkg_key(pkg, packages_arch):
        if binary:
            return pkg.name + ',' + pkg.arch + ',' + packages_arch
        else:
            return pkg.source

    logger.info('开始选择发布的软件包')
    best_versions = {}
    # 首先得到所选择的包的版本号
    for release in source_releases:
        this_versions = {}
        # 同一个系列中先确定最高版本
        for packages in release.all_packages.values() + release.all_sources.values():
            for pkg in packages:
                key = pkg_key(pkg, packages.arch)
                old_version = this_versions.get(key, '')
                if pkg <= old_version:
                    continue
                this_versions[key] = pkg.version
        # 然后按照指定策略更新至 best_version
        for key in this_versions:
            version = this_versions[key]
            old_version = best_versions.get(key, '')
            if policy == 'version':
                if utils.Version(version) <= old_version:
                    continue
            elif policy == 'first':
                if old_version:
                    continue
            best_versions[key] = version

    # 准备新的dist中的Packages
    new_packages = {}
    for release in source_releases:
        for fn in release.all_packages.keys() + release.all_sources.keys():
            newpath = os.path.join(topdir, target, fn)
            if not os.path.exists(newpath):
                try:
                    os.makedirs(os.path.dirname(newpath))
                except:
                    pass
            if fn not in new_packages:
                new_packages[fn] = utils.Packages(newpath)
    # 准备新dist中的Contents
    new_contents = {}
    if with_contents:
        for release in source_releases:
            for fn in release.all_contents.keys():
                newpath = os.path.join(topdir, target, fn)
                if not os.path.exists(newpath):
                    try:
                        os.makedirs(os.path.dirname(newpath))
                    except:
                        pass
                if fn not in new_contents:
                    new_contents[fn] = utils.Contents(newpath)

    # 把选中的包填入对应的Packages中，同时填充对应体系的Contents
    logger.info('生成合并后的Packages与Sources、Contents文件')
    for release in source_releases:
        for fn, packages in release.all_packages.items() + release.all_sources.items():
            for pkg in packages:
                if pkg == best_versions[pkg_key(pkg, packages.arch)]:
                    if with_contents:
                        contents_fn = 'Contents-' + packages.arch
                        source_contents = release.all_contents.get(contents_fn)
                        if source_contents:
                            try:
                                contents = new_contents.get(contents_fn)
                                pkg_fullname = source_contents.package_fullnames[pkg.name]
                                files = source_contents.packages[pkg.name]
                                contents.add_package(pkg_fullname, files)
                            except:
                                logger.warning(
                                    'Contents of %s:%s not found', pkg.name, pkg.arch)
                    new_packages[fn][pkg.name] = pkg

    # 保存Packages文件
    for packages in new_packages.values():
        packages.write()
    # 保存Contents文件
    if with_contents:
        for contents in new_contents.values():
            contents.write()

    # 生成release文件
    logger.info('生成合并后的Release文件')
    new_release = utils.Release(os.path.join(topdir, target, 'Release'))
    for release in source_releases:
        new_release.merge_data(release.data)
    new_release.data['Suite'] = target
    new_release.write()
    logger.info('合并完成')
    return True


def main(argv=None):
    """
    merge 2 or more suites into a new suite in the same archive
    """
    args = docopt.docopt(cmd_doc, argv, help=True, version='1.0')

    merge(topdir=os.path.abspath(args['--dir']),
          froms=[args['<source1>']] + args['<source2>'],
          target=args['--target'],
          policy=args['--policy'],
          binary=args['--binary'],
          force=args['--force'],
          with_contents=args['--contents']
          )
    return 0
