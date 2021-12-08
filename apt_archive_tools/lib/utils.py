# coding:utf-8

'''
Created on 2017-2-22

@author: xiewei
'''
import gzip
import os
import sys
import tempfile

import sqlite3
from io import BytesIO

import requests

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from collections import defaultdict

import re
pkg_field_pattern = re.compile(r'^(?P<key>[^\s:]*): (?P<value>.+)',
                               re.M)
src_field_pattern = re.compile(r'^(?P<key>[^\s:]*): (?P<value>.+)',
                               re.M)
source_version_pattern = re.compile(r'(.+) \((.+)\)')
files_pattern = re.compile(r'^ (\w{32})\s+(\d+) (.+)', re.M)
dependency_pattern = re.compile(r'\s*(\S+) \((\S+) (\S+)\)')

# cmp mixin
PY3 = sys.version_info[0] >= 3
if PY3:
    def cmp(a, b):
        return (a > b) - (a < b)
    # mixin class for Python3 supporting __cmp__

    class PY3__cmp__:
        def __eq__(self, other):
            return self.__cmp__(other) == 0

        def __ne__(self, other):
            return self.__cmp__(other) != 0

        def __gt__(self, other):
            return self.__cmp__(other) > 0

        def __lt__(self, other):
            return self.__cmp__(other) < 0

        def __ge__(self, other):
            return self.__cmp__(other) >= 0

        def __le__(self, other):
            return self.__cmp__(other) <= 0

        def __cmp__(self, other):
            return cmp(self, other)
else:
    class PY3__cmp__:
        pass


def read_url(url):
    if url.startswith('file://'):
        url = url[7:]
    if '://' not in url:
        # as file
        return open(url, 'rb').read()
    else:
        res_temp = requests.get(url, stream=True)
        state_tag = res_temp.status_code
        if state_tag == 200:
            return res_temp.content


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
        self.contents_files = {}
        self.hash_files = {}
        self.files_hash = {}

    def _parse(self):
        self.content = read_url(self.filepath)
        if isinstance(self.content, bytes):
            self.content = self.content.decode('utf-8')
        for k, v in re.findall(r'(\w+): ?(.+$)', self.content, re.M):
            self.data[k] = v

        self.files = [fileinfo[2]
                      for fileinfo in re.findall(files_pattern, self.content)]

        for md5sum, size, path in re.findall(files_pattern, self.content):
            self.hash_files[md5sum] = path
            self.files_hash[path] = md5sum

        return

    @staticmethod
    def parse(release_file):
        obj = Release(release_file)
        obj._parse()
        return obj

    @property
    def all_packages(self):
        self.load_index('Packages')
        return self.packages_files

    @property
    def all_sources(self):
        self.load_index('Sources')
        return self.sources_files

    @property
    def all_contents(self):
        self.load_index('Contents')
        return self.contents_files

    def load_index(self, name='Packages'):
        if name == 'Packages':
            index_list = self.packages_files
            pattern = re.compile(r'^Packages(\.gz){0,1}$')
            index_class = Packages
        elif name == 'Sources':
            index_list = self.sources_files
            pattern = re.compile(r'^Sources(\.gz){0,1}$')
            index_class = Sources
        elif name == 'Contents':
            index_list = self.contents_files
            pattern = re.compile(r'^Contents-\w+(\.gz){0,1}$')
            index_class = ContentsInDB
        else:
            raise NotImplementedError()

        if index_list:
            return
        for fn in self.files:
            match = pattern.match(os.path.basename(fn))
            if match:
                if match.groups()[0] == '.gz':
                    # gzipped
                    fpath = os.path.join(os.path.dirname(self.filepath), fn)
                    fn = fn.rsplit('.', 1)[0]
                else:
                    fpath = os.path.join(os.path.dirname(self.filepath), fn)
            else:
                continue

            if fn in index_list:
                # 已经统计的
                continue
            url_tag = re.findall(
                r"^((https?|ftp)://|(www|ftp)\.)[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+([/?].*)?$", fpath)
            if url_tag:
                res_temp = requests.head(fpath)
                state_tag = res_temp.status_code
                if state_tag == 200:
                    index_list[fn] = index_class.parse(fpath)
            else:
                if not os.path.isfile(fpath):
                    # 已经删除了的索引文件就不要管了
                    continue
                if os.path.exists(fpath):
                    index_list[fn] = index_class.parse(fpath)
        return

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
        with open(tmpconf, 'wb') as f:
            if not isinstance(conf, bytes):
                conf = conf.encode('utf-8')
            f.write(conf)
        # generate Release
        topdir = os.path.dirname(self.filepath)
        os.system(
            'rm -f "%(top)s"/InRelease "%(top)s"/Release.gpg "%(top)s"/Release' % {'top': topdir})

        content = os.popen('apt-ftparchive -c %(conf)s release %(top)s --contents' % {'conf': tmpconf,
                                                                                      'top': topdir
                                                                                      }
                           ).read()
        with open(os.path.join(topdir, 'Release'), 'w') as f:
            f.write(content)
        # remove Packages and Sources
        from .sign import sign_file
        sign_file(topdir)
        return

    def merge_data(self, other_data):
        """
        merge release data to current
        """
        # special: Components, Architectures
        for key in other_data:
            other_value = other_data.get(key, '')
            if key in ['Components', 'Architectures']:
                new_set = set(self.data.get(key, '').split()
                              ) | set(other_value.split())
                self.data[key] = ' '.join(new_set)
            else:
                self.data[key] = other_value


class Packages(object):
    """
    Packages文件的内容，读取、解析包列表、保存
    """

    def __init__(self, filepath):
        self.filepath = filepath
        match = re.search(r'binary-(.*)/Packages', self.filepath)
        if match:
            self.arch = match.groups()[0]
        elif re.search('source/Sources', self.filepath):
            self.arch = 'src'
        else:
            self.arch = ''
        self.data = {}

    def _read(self):
        read_temp_data = read_url(self.filepath)
        if self.filepath.endswith('.gz'):
            self.filepath = self.filepath.rsplit('.', 1)[0]
            try:
                data = gzip.GzipFile(fileobj=BytesIO(read_temp_data)).read()
            except:
                data = read_temp_data
        else:
            data = read_temp_data

        if PY3:
            return data.decode('utf-8')
        else:
            return data

    def _parse(self):
        temp = self._read()
        sections = temp.strip().split('\n\n')
        for section in sections:
            if not section.strip():
                continue
            package = Package(section)
            # 同一个Packages里还有重复的，所以需要保留版本号最高的那个
            old_version = self.data.get(package.name, '')
            if package > old_version:
                self.data[package.name] = package
        return self.data

    @staticmethod
    def parse(packages_file):
        obj = Packages(packages_file)
        obj._parse()
        return obj

    @staticmethod
    def zip_packages(packagesfile, content=None):
        """
        根据Packages生成Packages.gz
        """
        if not content:
            with open(packagesfile, 'rb') as f:
                content = f.read()
        # gz
        zfile = gzip.open(packagesfile + '.gz', mode='wb')
        zfile.write(content)
        zfile.close()
        return

    def write(self, newpath=None, backup=''):
        """
        包列表写入Packages，并生成Packages.gz
        """
        filepath = newpath or self.filepath
        # create a origin backup
        if backup and os.path.exists(filepath):
            os.rename(filepath, filepath + '.' + backup)
        # write new
        with open(filepath, 'w', encoding='utf-8') as f:
            for pkg_name in sorted(self.data.keys()):
                f.write(str(self.data[pkg_name]) + '\n\n')
        # remove compressed
        for ext in ['.gz', '.bz2', '.xz']:
            compressed_file = filepath + ext
            if os.path.exists(compressed_file):
                os.unlink(compressed_file)
        self.zip_packages(filepath)
        return

    def __setitem__(self, key, item):
        self.data[key] = item

    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        for v in self.data.values():
            yield v


class Package(PY3__cmp__, object):
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

    @property
    def size(self):
        return int(self.data['Size'])

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
        temp = self._read()
        sections = temp.strip().split('\n\n')
        for section in sections:
            if not section.strip():
                continue
            source = Source(section)
            self.data[source.name] = source
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


class Version(PY3__cmp__, object):
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


class Contents(object):
    """parse Contents file"""

    def __init__(self, filepath, arch=''):
        """
        filepath like [path-to]/Contents-[arch]
        """
        self.filepath = filepath
        self.packages = defaultdict(list)
        self.package_fullnames = {}  # busybox -> utils/busybox
        self.files = defaultdict(set)
        self.arch = arch or os.path.splitext(filepath)[0].split('-')[-1]

    @staticmethod
    def parse(contents_file):
        obj = Contents(contents_file)
        obj._parse()
        return obj

    def _read(self):
        read_temp_data = read_url(self.filepath)
        if self.filepath.endswith('.gz'):
            self.filepath = self.filepath.rsplit('.', 1)[0]
            try:
                data = gzip.GzipFile(fileobj=BytesIO(read_temp_data)).read()
            except:
                data = read_temp_data
        else:
            data = read_temp_data

        if PY3:
            return data.decode('utf-8')
        else:
            return data

    def _parse(self):
        temp = self._read()
        for line in temp.split('\n'):
            if not line:
                break
            self._parse_line(line)

    def _parse_line(self, line):
        """
        导入Contents文件中的一行数据
        """
        filename, packages = line.rsplit(None, 1)
        for package in packages.split(','):
            self.files[filename].add(package)
            package_name = package.split('/')[-1]
            self.package_fullnames[package_name] = package
            self.packages[package_name].append(filename)

    def write(self, newpath=None, backup=''):
        """
        文件-包的对应关系列表写入Contents，并生成Contents.gz
        """
        filepath = newpath or self.filepath
        # create a origin backup
        if backup and os.path.exists(filepath):
            os.rename(filepath, filepath + '.' + backup)
        # write new
        with open(filepath, 'w') as f:
            for filename in sorted(self.files.keys()):
                packages = self.files[filename]
                f.write(filename + '\t' * 5 + ','.join(packages) + '\n')
        self.zip_contents(filepath)

    @staticmethod
    def zip_contents(contents_file, content=None):
        """
        根据Contents生成Contents.gz
        """
        if not content:
            with open(contents_file, 'rb') as f:
                content = f.read()
        # gz and bz2
        zfile = gzip.open(contents_file + '.gz', mode='wb')
        zfile.write(content)
        zfile.close()

    def remove_package(self, package):
        file_list = self.packages.pop(package)
        package_fullname = self.package_fullnames[package]
        for filename in file_list:
            self.files[filename].remove(package_fullname)

    def remove_file(self, filename):
        packages = self.files.pop(filename)
        for package in packages:
            package_name = package.split('/')[-1]
            self.packages[package_name].remove(filename)

    def add_package(self, package, file_list):
        package_name = package.split('/')[-1]
        self.package_fullnames[package_name] = package
        self.packages[package_name] = file_list
        for file_name in file_list:
            self.files[file_name].add(package)


class ContentsInDB(object):
    """
    利用sqlite db保存Contents信息
    """

    def __init__(self, filepath, arch=''):
        """
        filepath like [path-to]/Contents-[arch]
        """
        self.dbfile = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.dbfile)
        # self.db.text_factory = str
        self.filepath = filepath
        self.arch = arch or os.path.splitext(filepath)[0].split('-')[-1]

    def _create_table(self):
        cu = self.db.cursor()
        cu.execute('create table file (file ntext, package_name, package)')
        self.db.commit()

    @staticmethod
    def parse(contents_file):
        obj = ContentsInDB(contents_file)
        obj._parse()
        return obj

    def _read(self):
        read_temp_data = read_url(self.filepath)
        if self.filepath.endswith('.gz'):
            self.filepath = self.filepath.rsplit('.', 1)[0]
            try:
                data = gzip.GzipFile(fileobj=BytesIO(read_temp_data)).read()
            except:
                data = read_temp_data
        else:
            data = read_temp_data

        if PY3:
            return data.decode('utf-8')
        else:
            return data

    def _parse(self):
        temp = self._read()
        self._create_table()
        for line in temp.split('\n'):
            if not line:
                break
            self._parse_line(line)
        self.db.commit()

    def _parse_line(self, line):
        """
        导入Contents文件中的一行数据
        """
        filename, packages = line.rsplit(None, 1)
        cu = self.db.cursor()
        for package in packages.split(','):
            package_name = package.split('/')[-1]
            cu.execute("insert into file values (?,?,?)",
                       (filename.decode('latin-1'),
                        package_name,
                        package
                        ))

    def write(self, newpath=None, backup=''):
        """
        文件-包的对应关系列表写入Contents，并生成Contents.gz
        """
        filepath = newpath or self.filepath
        # create a origin backup
        if backup and os.path.exists(filepath):
            os.rename(filepath, filepath + '.' + backup)
        # write new
        with open(filepath, 'wb') as f:
            cur = self.db.cursor()
            cur.execute('select * from file order by file')
            last_file = ''
            while 1:
                row = cur.fetchone()
                if not row:
                    break
                filename = row[0].encode('latin-1')
                if filename != last_file:
                    if last_file:
                        f.write('\n')
                    f.write(filename + '\t' * 5 + row[2].encode('latin-1'))
                    last_file = filename
                else:
                    f.write(',' + row[2])
            f.write('\n')
        self.zip_contents(filepath)

    @staticmethod
    def zip_contents(contents_file, content=None):
        """
        根据Contents生成Contents.gz
        """
        if not content:
            with open(contents_file, 'rb') as f:
                content = f.read()
        # gz
        zfile = gzip.open(contents_file + '.gz', mode='wb')
        zfile.write(content)
        zfile.close()

    def remove_package(self, package):
        cur = self.db.cursor()
        cur.execute('delete from file where package_name=?', (package,))
        self.db.commit()

    def remove_file(self, filename):
        cur = self.db.cursor()
        cur.execute('delete from file where file=?', (filename,))
        self.db.commit()

    def add_package(self, package, file_list):
        package_name = package.split('/')[-1]
        cur = self.db.cursor()
        for filename in file_list:
            cur.execute('insert into file values (?,?,?)',
                        (filename, package_name, package))
        self.db.commit()

    def files_of_package(self, package_name):
        cur = self.db.cursor()
        cur.execute('select * from file where package_name=?', (package_name,))
        return cur.fetchall()

    def __del__(self):
        """
        自动删除临时数据库
        """
        self.db.close()
        os.unlink(self.dbfile)


def strip_packages(packagesfile):
    """
    remove lower version from Packages file
    """
    packages = Packages.parse(packagesfile)
    packages.write()
    return


def file_hash(filepath, hash_name='md5'):
    import hashlib
    h = hashlib.new(hash_name)
    f = open(filepath, 'r')
    while True:
        # 每次读取1M放到 data 中
        data = f.read(1024 * 1024)
        size = len(data)
        if not size:
            # 数据流已经读取完毕
            break
        # 校验器校验一下
        h.update(data)
    f.close()
    return h.hexdigest()
