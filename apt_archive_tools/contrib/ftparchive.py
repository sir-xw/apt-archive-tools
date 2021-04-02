# Copyright 2009-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
import os
import subprocess
import shutil
import errno
import re
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import time
import tempfile

import logging
logger = logging.getLogger('archive_man')


def open_for_writing(filename, mode, dirmode=0o777):
    """Open 'filename' for writing, creating directories if necessary.

    :param filename: The path of the file to open.
    :param mode: The mode to open the filename with. Should be 'w', 'a' or
        something similar. See ``open`` for more details. If you pass in
        a read-only mode (e.g. 'r'), then we'll just accept that and return
        a read-only file-like object.
    :param dirmode: The mode to use to create directories, if necessary.
    :return: A file-like object that can be used to write to 'filename'.
    """
    try:
        return open(filename, mode)
    except IOError as e:
        if e.errno == errno.ENOENT:
            os.makedirs(os.path.dirname(filename), mode=dirmode)
            return open(filename, mode)


def write_file(path, content):
    with open_for_writing(path, 'w') as f:
        f.write(content)


def package_name(filename):
    """Extract a package name from a debian package filename."""
    return (os.path.basename(filename).split("_"))[0]


def make_clean_dir(path, clean_pattern=".*"):
    """Ensure that the path exists and is an empty directory.

    :param clean_pattern: a regex of filenames to remove from the directory.
        If omitted, all files are removed.
    """
    if os.path.isdir(path):
        for name in os.listdir(path):
            if name == "by-hash" or not re.match(clean_pattern, name):
                # Ignore existing by-hash directories; they will be cleaned
                # up to match the rest of the directory tree later.
                continue
            child_path = os.path.join(path, name)
            # Directories containing index files should never have
            # subdirectories other than by-hash.  Guard against expensive
            # mistakes by not recursing here.
            os.unlink(child_path)
    else:
        os.makedirs(path, 0o755)


DEFAULT_COMPONENT = "main"

CONFIG_HEADER = """
Dir
{
    ArchiveDir "%s";
    OverrideDir "%s";
    CacheDir "%s";
};

Default
{
    Contents::Compress "gzip";
    DeLinkLimit 0;
    MaxContentsChange 12000;
    FileMode 0644;
}

TreeDefault
{
    Contents "$(DIST)/Contents-$(ARCH)";
};

"""

STANZA_TEMPLATE = """
tree "%(DISTS)s/%(DISTRORELEASEONDISK)s"
{
    FileList "%(LISTPATH)s/%(DISTRORELEASEBYFILE)s_$(SECTION)_binary-$(ARCH)";
    SourceFileList "%(LISTPATH)s/%(DISTRORELEASE)s_$(SECTION)_source";
    Sections "%(SECTIONS)s";
    Architectures "%(ARCHITECTURES)s";
    # BinOverride "override.%(DISTRORELEASE)s.$(SECTION)";
    BinOverride "";
    # SrcOverride "override.%(DISTRORELEASE)s.$(SECTION).src";
    SrcOverride "";
    # %(HIDEEXTRA)sExtraOverride "override.%(DISTRORELEASE)s.extra.$(SECTION)";
    %(HIDEEXTRA)sExtraOverride "";
    Packages::Extensions "%(EXTENSIONS)s";
    Packages::Compress "%(COMPRESSORS)s";
    Sources::Compress "%(COMPRESSORS)s";
    Contents::Compress ". gzip";
    Translation::Compress "%(COMPRESSORS)s";
    BinCacheDB "packages%(CACHEINSERT)s-$(ARCH).db";
    SrcCacheDB "sources%(CACHEINSERT)s.db";
    LongDescription "%(LONGDESCRIPTION)s";
}

"""

EXT_TO_SUBCOMPONENT = {
    'udeb': 'debian-installer',
    'ddeb': 'debug',
}

SUBCOMPONENT_TO_EXT = {
    'debian-installer': 'udeb',
    'debug': 'ddeb',
}

CLEANUP_FREQUENCY = 60 * 60 * 24

COMPRESSOR_TO_CONFIG = {
    '': '.',
    'gz': 'gzip',
}


class AptFTPArchiveFailure(Exception):
    """Failure while running apt-ftparchive."""


class FTPArchiveHandler:
    """Produces Sources and Packages files via apt-ftparchive.

    Generates file lists and configuration for apt-ftparchive, and kicks
    off generation of the Sources and Releases files.
    """

    def __init__(self, archiveroot, archs, suite, components=None, with_contents=False):
        self.tmpdir = tempfile.mkdtemp(prefix='apt')
        self.overrideroot = os.path.join(self.tmpdir, 'override')
        self.miscroot = os.path.join(self.tmpdir, 'misc')
        self.cacheroot = os.path.join(self.tmpdir, 'cache')

        self.archiveroot = archiveroot
        self.distsroot = os.path.join(self.archiveroot, 'dists')
        self.pool = os.path.join(self.archiveroot, 'pool')
        self.suite = suite
        self.archs = archs
        self.with_contents = with_contents
        self.components = components or [DEFAULT_COMPONENT]
        self.subcomponents = set()
        self.pool_files = []

    def run(self):
        """Do the entire generation and run process."""
        self.createEmptyPocketRequests()
        logger.debug("Generating file lists.")
        self.generateFileLists()
        logger.debug("Doing apt-ftparchive work.")
        apt_config_filename = self.generateConfig()
        self.generateDistTree()
        self.runApt(apt_config_filename)
        self.cleanCaches()

    def runAptWithArgs(self, apt_config_filename, *args):
        """Run apt-ftparchive in subprocesses.

        :raise: AptFTPArchiveFailure if any of the apt-ftparchive
            commands failed.
        """
        logger.debug("Filepath: %s" % apt_config_filename)

        base_command = ["apt-ftparchive"] + list(args) + [apt_config_filename]
        ret = subprocess.call(base_command)

        if ret != 0:
            raise AptFTPArchiveFailure("apt-ftparchive failed")

    def runApt(self, apt_config_filename):
        if self.with_contents:
            self.runAptWithArgs(apt_config_filename, "generate")
        else:
            self.runAptWithArgs(apt_config_filename, "--no-contents", "generate")

    #
    # Empty Pocket Requests
    #
    def createEmptyPocketRequests(self):
        """Write out empty file lists etc for pockets.

        We do this to have Packages or Sources for them even if we lack
        anything in them currently.
        """
        make_clean_dir(self.miscroot)
        make_clean_dir(self.cacheroot)
        for comp in self.components:
            self.createEmptyPocketRequest(comp)

    def createEmptyPocketRequest(self, comp):
        """Creates empty files for a release component"""
        # Create empty override lists.
        needed_paths = [
            (comp,),
            ("extra", comp),
            (comp, "src"),
        ]
        for sub_comp in self.subcomponents:
            needed_paths.append((comp, sub_comp))

        for path in needed_paths:
            write_file(os.path.join(
                self.overrideroot,
                ".".join(("override", self.suite) + path)), "")

        # Create empty file lists.
        def touch_list(*parts):
            write_file(os.path.join(
                self.overrideroot,
                "_".join((self.suite, ) + parts)), "")
        touch_list(comp, "source")

        for arch in self.archs:
            # Touch more file lists for the archs.
            touch_list(comp, "binary-" + arch)
            for sub_comp in self.subcomponents:
                touch_list(comp, sub_comp, "binary-" + arch)

    #
    # File List Generation
    #
    def getPoolFiles(self):
        for folder, _dirlist, filelist in os.walk(self.pool):
            for filename in filelist:
                filepath = os.path.join(folder, filename)
                try:
                    ext = filename.rsplit('.', 1)[1]
                except:
                    continue
                subcomp = EXT_TO_SUBCOMPONENT.get(ext)
                if subcomp != None:
                    self.subcomponents.add(subcomp)
                if ext.endswith('deb'):
                    arch = os.path.splitext(filename)[0].split('_')[-1]
                else:
                    arch = 'source'
                self.pool_files.append((filepath, arch, subcomp))

    def generateFileLists(self):
        """Collect currently published FilePublishings and write filelists."""
        self.getPoolFiles()
        self.publishFileLists()

    def publishFileLists(self):
        """Collate the set of source files and binary files provided and
        write out all the file list files for them.

        listroot/distroseries_component_source
        listroot/distroseries_component_binary-archname
        """
        filelist = defaultdict(lambda: defaultdict(list))

        def updateFileInfoList(filepath, arch, subcomp):
            topname = filepath[len(self.pool):].strip('/').split('/')[0]
            if topname in self.components:
                component = topname
            else:
                component = DEFAULT_COMPONENT
                if component not in self.components:
                    self.components.append(component)
            if arch == 'all':
                for arch1 in self.archs:
                    filelist[component][arch1].append((filepath, subcomp))
            else:
                filelist[component][arch].append((filepath, subcomp))

        logger.debug("Calculating pool filelist.")
        for fileinfo in self.pool_files:
            updateFileInfoList(*fileinfo)

        logger.debug("Writing file lists for %s" % self.suite)
        for component, architectures in filelist.items():
            for architecture, file_infos in architectures.items():
                self.writeFileList(
                    architecture, file_infos, component)

    def writeFileList(self, arch, file_infos, component):
        """Output file lists for a series and architecture.

        This includes the subcomponent file lists.
        """
        files = defaultdict(list)
        for name, subcomp in file_infos:
            files[subcomp].append(name)

        if arch != 'source':
            arch = 'binary-' + arch

        lists = (
            [(None, 'regular', '%s_%s_%s' % (self.suite, component, arch))]
            + [(subcomp, subcomp,
                '%s_%s_%s_%s' % (self.suite, component, subcomp, arch))
               for subcomp in self.subcomponents])
        for subcomp, desc, filename in lists:
            logger.debug(
                "Writing %s file list for %s/%s/%s" % (
                    desc, self.suite, component, arch))
            path = os.path.join(self.overrideroot, filename)
            with open(path, "w") as f:
                files[subcomp].sort(key=package_name)
                f.write("\n".join(files[subcomp]))
                f.write("\n")

    #
    # Config Generation
    #
    def generateConfig(self):
        """Generate an APT FTPArchive configuration from the provided
        config object and the paths we either know or have given to us.
        """
        apt_config = StringIO()
        apt_config.write(CONFIG_HEADER % (self.archiveroot,
                                          self.overrideroot,
                                          self.cacheroot
                                          ))

        self.writeAptConfig(
            apt_config,
            ["", "gz"])

        self.generateDistTree()

        apt_config_filename = os.path.join(self.miscroot, "apt.conf")
        with open(apt_config_filename, "w") as fp:
            fp.write(apt_config.getvalue())
        apt_config.close()
        return apt_config_filename

    def generateDistTree(self):
        # Make sure all the relevant directories exist and are empty.  Each
        # of these only contains files generated by apt-ftparchive, and may
        # contain files left over from previous configurations (e.g.
        # different compressor types).
        for comp in self.components:
            component_path = os.path.join(
                self.distsroot, self.suite, comp)
            make_clean_dir(os.path.join(component_path, "source"))
            for arch in self.archs:
                make_clean_dir(os.path.join(component_path, "binary-" + arch))
                for subcomp in self.subcomponents:
                    make_clean_dir(os.path.join(
                        component_path, subcomp, "binary-" + arch))

    def writeAptConfig(self, apt_config,
                       index_compressors):
        logger.debug("Generating apt config for %s" % self.suite)
        compressors = " ".join(
            COMPRESSOR_TO_CONFIG[c] for c in index_compressors)
        apt_config.write(STANZA_TEMPLATE % {
                         "LISTPATH": self.overrideroot,
                         "DISTRORELEASE": self.suite,
                         "DISTRORELEASEBYFILE": self.suite,
                         "DISTRORELEASEONDISK": self.suite,
                         "ARCHITECTURES": " ".join(self.archs + ["source"]),
                         "SECTIONS": " ".join(self.components),
                         "EXTENSIONS": ".deb",
                         "COMPRESSORS": compressors,
                         "CACHEINSERT": "",
                         "DISTS": os.path.basename(self.distsroot),
                         "HIDEEXTRA": "",
                         "LONGDESCRIPTION": "true"
                         })

        if self.archs:
            for component in self.components:
                for subcomp in self.subcomponents:
                    apt_config.write(STANZA_TEMPLATE % {
                        "LISTPATH": self.overrideroot,
                        "DISTRORELEASEONDISK": "%s/%s" % (self.suite, component),
                        "DISTRORELEASEBYFILE": "%s_%s" % (self.suite, component),
                        "DISTRORELEASE": "%s.%s" % (self.suite, component),
                        "ARCHITECTURES": " ".join(self.archs),
                        "SECTIONS": subcomp,
                        "EXTENSIONS": '.%s' % SUBCOMPONENT_TO_EXT[subcomp],
                        "COMPRESSORS": compressors,
                        "CACHEINSERT": "-%s" % subcomp,
                        "DISTS": os.path.basename(self.distsroot),
                        "HIDEEXTRA": "// ",
                        "LONGDESCRIPTION": "true",
                    })

    def cleanCaches(self):
        shutil.rmtree(self.tmpdir)


if __name__ == "__main__":
    handler = FTPArchiveHandler('/home/xiewei/apt-mirrors/strip-test',
                                archs=['arm64', 'amd64', 'i386', 'armhf'],
                                suite='juniper',
                                components=['contrib'])
    handler.run()
