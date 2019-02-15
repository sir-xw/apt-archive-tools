# encoding: utf-8
'''
Created on 2016-6-23

@author: xiewei

根据自定义包集合发布软件源

'''

from ..contrib import docopt
import os
import subprocess
import logging
from .config import options

logger = logging.getLogger('archive_man')

cmd_doc = """
Usage:
   archive_man publish <topdir> [-s <suite>] [-v <version>] [-a <architecture>...] [-d <description>]

Options:
   -h, --help              show this help.
   -s,--suite=<suite>      set codename of archive. [default: %(suite)s]
   -v,--version=<version>  set version info of archive [default: 1.0].
   -a,--architecture=<architecture>
                           set architectures in archive, May be specified
                           multiple times. Specially, add 'src' in architectures
                           can generate sources index.
                           [default: %(arch)s]
   -d,--description=<description>
                           set description in Release.
""" % options


def _verify_args(args):
    data = {}
    data['Architectures'] = ' '.join(args['--architecture'])
    data['Version'] = args['--version']
    data['Suite'] = args['--suite']
    data['Codename'] = args['--suite']
    data['Components'] = 'main'
    data['Description'] = args.get('--description', 'Customized archive.')
    data['topdir'] = os.path.abspath(os.path.expanduser(args['<topdir>']))
    return data


def gen_packages(topdir, dist, arch, component='main'):
    logger.info('generating Packages file for %s', arch)
    if arch == 'src':
        index_dir = os.path.join(topdir, 'dists', dist,
                                component, 'source')
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
        packagefile = os.path.join(index_dir, 'Sources')
        cmd = 'apt-ftparchive sources pool > "%s"' % packagefile
    else:
        index_dir = os.path.join(topdir, 'dists', dist,
                                component, 'binary-' + arch)
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
        packagefile = os.path.join(index_dir, 'Packages')
        cmd = 'apt-ftparchive --arch=%s packages pool > "%s"' % (arch, packagefile)
    ret = subprocess.call(cmd,
                          cwd=topdir, shell=True
                          )
    if ret == 0:
        from .utils import strip_packages
        strip_packages(packagefile)  # will also compress Packages file
    return ret == 0


def gen_release(topdir, data):
    logger.info('generating Release file')
    data['Origin'] = 'apt-archive'
    data['Label'] = 'Apt Archive'

    conf = """APT::FTPArchive::Release {
Origin "%(Origin)s";
Label "%(Label)s";
Suite "%(Suite)s";
Codename "%(Codename)s";
Version "%(Version)s";
Architectures "%(Architectures)s";
Components "%(Components)s";
Description "%(Description)s";
};
""" % data
    # write conf
    import tempfile
    tmpconf = tempfile.mktemp('.conf')
    with open(tmpconf, 'w') as f:
        f.write(conf)
    # generate Release
    os.system(
        'rm -f "%(top)s"/InRelease "%(top)s"/Release.gpg "%(top)s"/Release' % {'top': topdir})
    content = os.popen('apt-ftparchive -c %(conf)s release %(top)s' % {'conf': tmpconf,
                                                                       'top': topdir
                                                                       }
                       ).read()
    with open(os.path.join(topdir, 'Release'), 'w') as f:
        f.write(content)
    logger.info('built Release in %s' % topdir)
    from .sign import sign_file
    sign_file(topdir)


def publish_archive(data):
    pool = os.path.join(data['topdir'], 'pool')
    dists = os.path.join(data['topdir'], 'dists', data['Suite'])
    if not os.path.isdir(pool):
        logger.error('%s is not a directory' % pool)
        return 1
    if not os.path.exists(dists):
        os.makedirs(dists)
    # generate packages
    component = data['Components'].split()[0]
    for arch in data['Architectures'].split():
        if gen_packages(topdir=data['topdir'],
                        dist=data['Suite'],
                        arch=arch,
                        component=component
                        ):
            continue
        else:
            return 1

    # generate release
    gen_release(dists, data)
    logger.info('archive published. Source: deb file://%s %s %s' % (data['topdir'],
                                                                    data['Suite'],
                                                                    component
                                                                    )
                )
    return 0


def main(argv=None):
    """
    publish a customized archive form a package pool
    """
    args = docopt.docopt(cmd_doc, argv, help=True)
    ret = publish_archive(_verify_args(args))
    return ret
