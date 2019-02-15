# coding:utf-8

'''
Created on 2017-2-22

@author: xiewei
'''
import os
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import re
pkg_fields = ['Package', 'Version', 'Architecture', 'Source',
              'Filename', 'Depends', 'Pre-depends', 'Provides', 'MD5sum', 'Size']
pkg_field_pattern = re.compile(r'^(?P<key>' + '|'.join(pkg_fields) + '): (?P<value>.+)',
                               re.M)
src_field_pattern = re.compile(r'^(?P<key>Package|Version|Directory): (?P<value>.+)',
                               re.M)
source_version_pattern = re.compile(r'(.+) \((.+)\)')
files_pattern = re.compile(r'^ (\w{32})\s+(\d+) (.+)', re.M)
dependency_pattern = re.compile(r'\s*(\S+) \((\S+) (\S+)\)')


class Release(object):
    """
    Release文件的内容，提供读取、保存等功能
    """

    def __init__(self, filepath):
        self.filepath = filepath
        self.data = OrderedDict()
        self.files = []
        self.packages_files = {}
        self.sources_files = {}

    def _parse(self):
        with open(self.filepath) as f:
            self.content = f.read()
        for k, v in re.findall(r'(\w+): ?(.+$)', self.content, re.M):
            self.data[k] = v

        self.files = [fileinfo[2] for fileinfo in re.findall(files_pattern, self.content)]

        return

    @staticmethod
    def parse(release_file):
        obj = Release(release_file)
        obj._parse()
        return obj

    @property
    def all_packages(self):
        if not self.packages_files:
            for fn in self.files:
                if os.path.basename(fn) == 'Packages':
                    fpath = os.path.join(os.path.dirname(self.filepath), fn)
                    if not os.path.isfile(fpath):
                        # 已经删除了的索引文件就不要管了
                        continue
                    packages = Packages.parse(fpath)
                    self.packages_files[fn] = packages
        if not self.packages_files:
            # gzipped
            for fn in self.files:
                if os.path.basename(fn) == 'Packages.gz':
                    fpath = os.path.join(os.path.dirname(self.filepath), fn)
                    if not os.path.isfile(fpath):
                        # 已经删除了的索引文件就不要管了
                        continue
                    packages = Packages.parse(fpath)
                    self.packages_files[fn.rsplit('.', 1)[0]] = packages

        return self.packages_files

    @property
    def all_sources(self):
        if not self.sources_files:
            for fn in self.files:
                if os.path.basename(fn) == 'Sources':
                    fpath = os.path.join(os.path.dirname(self.filepath), fn)
                    if not os.path.isfile(fpath):
                        # 已经删除了的索引文件就不要管了
                        continue
                    sources = Sources.parse(fpath)
                    self.sources_files[fn] = sources
        if not self.sources_files:
            # gzipped
            for fn in self.files:
                if os.path.basename(fn) == 'Sources.gz':
                    fpath = os.path.join(os.path.dirname(self.filepath), fn)
                    if not os.path.isfile(fpath):
                        # 已经删除了的索引文件就不要管了
                        continue
                    sources = Sources.parse(fpath)
                    self.sources_files[fn.rsplit('.', 1)[0]] = sources
        return self.sources_files

    def write(self):
        conf = 'APT::FTPArchive::Release {'
        for k, v in self.data.items():
            if k == 'Date':
                continue
            conf += '%s "%s";' % (k, v)
        conf += '};'

        # write conf
        import tempfile
        tmpconf = tempfile.mktemp('.conf')
        with open(tmpconf, 'w') as f:
            f.write(conf)
        # generate Release
        topdir = os.path.dirname(self.filepath)
        os.system(
            'rm -f "%(top)s"/InRelease "%(top)s"/Release.gpg "%(top)s"/Release' % {'top': topdir})

        content = os.popen('apt-ftparchive -c %(conf)s release %(top)s' % {'conf': tmpconf,
                                                                           'top': topdir
                                                                           }
                           ).read()
        with open(os.path.join(topdir, 'Release'), 'w') as f:
            f.write(content)

        from .sign import sign_file
        sign_file(topdir)
        return


class Packages(object):
    """
    Packages文件的内容，读取、解析包列表、保存
    """

    def __init__(self, filepath):
        self.filepath = filepath
        self.data = {}

    def _parse(self):
        if self.filepath.endswith('.gz'):
            import gzip
            f = gzip.open(self.filepath)
            self.filepath = self.filepath.rsplit('.', 1)[0]
        else:
            f = open(self.filepath)
        sections = f.read().strip().split('\n\n')
        for section in sections:
            if not section.strip():
                continue
            package = Package(section)
            # 同一个Packages里还有重复的，所以需要保留版本号最高的那个
            old_version = self.data.get(package.name, '')
            if package > old_version:
                self.data[package.name] = package
        f.close()
        return self.data

    @staticmethod
    def parse(packages_file):
        obj = Packages(packages_file)
        obj._parse()
        return obj

    @staticmethod
    def zip_packages(packagesfile, content=None):
        """
        根据Packages生成Packages.gz,Packages.bz2
        """
        if not content:
            with open(packagesfile) as f:
                content = f.read()
        # gz and bz2
        import gzip
        zfile = gzip.open(packagesfile + '.gz', mode='w')
        zfile.write(content)
        zfile.close()
        import bz2
        with open(packagesfile + '.bz2', 'w') as f:
            f.write(bz2.compress(content))
        return

    def write(self, newpath=None, backup=''):
        """
        包列表写入Packages，并生成Packages.gz,Packages.bz2
        """
        filepath = newpath or self.filepath
        # create a origin backup
        if backup and os.path.exists(filepath):
            os.rename(filepath, filepath + '.' + backup)
        # write new
        with open(filepath, 'w') as f:
            for pkg_name in sorted(self.data.keys()):
                f.write(str(self.data[pkg_name]) + '\n\n')
        self.zip_packages(filepath)
        return

    def __setitem__(self, key, item):
        self.data[key] = item

    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        return self.data.itervalues()


class Package(object):
    """
    Packages 文件中的单个记录
    """
    __slots__ = ['text', 'data']

    def __init__(self, text):
        self.text = text
        self.data = dict(re.findall(pkg_field_pattern, self.text))
        if 'Source' in self.data:
            source = self.data['Source']
            try:
                # 有的包版本号与源码版本号不一样
                sourcename, sourceversion = re.match(
                    source_version_pattern, source).groups()
                self.data['Source'] = sourcename
                self.data['SourceVersion'] = sourceversion
            except:
                self.data['SourceVersion'] = self.data['Version']
        else:
            self.data['Source'] = self.data['Package']
            self.data['SourceVersion'] = self.data['Version']

    @property
    def name(self):
        return self.data['Package']

    @property
    def source(self):
        return self.data['Source']

    @property
    def version(self):
        return self.data['SourceVersion']

    @property
    def binary_version(self):
        return Version(self.data['Version'])

    @property
    def arch(self):
        return self.data['Architecture']

    @property
    def filename(self):
        return self.data['Filename']
    
    @property
    def md5sum(self):
        return self.data['MD5sum']

    def __str__(self):
        return self.text

    def __cmp__(self, other):
        return Version(self.version).__cmp__(other)

    @property
    def provides(self):
        l = []
        for i in self.data.get('Provides', '').split(','):
            j = i.strip()
            if j:
                l.append(j)
        return l

    @property
    def dependencies(self):
        dep_list = []
        for key in ['Depends', 'Pre-Depends']:
            for dep1 in self.data.get(key, '').split(','):
                dep_group = []
                for dep in dep1.split('|'):
                    try:
                        dep_group.append(
                            re.match(dependency_pattern, dep).groups())
                    except AttributeError:
                        depon = dep.strip()
                        if depon:
                            dep_group.append((depon, '', ''))
                dep_list.append(dep_group)
        return dep_list


class Sources(Packages):
    def _parse(self):
        if self.filepath.endswith('.gz'):
            import gzip
            f = gzip.open(self.filepath)
            self.filepath = self.filepath.rsplit('.', 1)[0]
        else:
            f = open(self.filepath)
        sections = f.read().strip().split('\n\n')
        for section in sections:
            if not section.strip():
                continue
            source = Source(section)
            self.data[source.name] = source
        f.close()
        return self.data

    @staticmethod
    def parse(sources_file):
        obj = Sources(sources_file)
        obj._parse()
        return obj


class Source(Package):
    __slots__ = []

    def __init__(self, text):
        self.text = text

        self.data = dict(re.findall(src_field_pattern, self.text))
        self.data['Source'] = self.data['Package']
        self.data['SourceVersion'] = self.data['Version']
        self.data['files'] = re.findall(files_pattern, self.text)

    @property
    def files(self):
        directory = self.data['Directory']
        return [directory + '/' + fileinfo[2] for fileinfo in self.data['files']]

    @property
    def fileinfos(self):
        directory = self.data['Directory']
        return [(md5, size, directory + '/' + filename) for md5, size, filename in self.data['files']]

    @property
    def arch(self):
        return 'src'


class Version(object):
    def __init__(self, value):
        self.version = value

    def __repr__(self, *args, **kwargs):
        return self.version

    def __cmp__(self, other):
        import apt
        try:
            other_version = other.version
        except:
            other_version = str(other)
        return apt.apt_pkg.version_compare(self.version, other_version)

def strip_packages(packagesfile):
    """
    remove lower version from Packages file
    """
    packages = Packages.parse(packagesfile)
    packages.write()
    return