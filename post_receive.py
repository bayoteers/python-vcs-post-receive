#!/usr/bin/python -tt
#
# vim: sw=4 ts=4 expandtab ai
#
# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# 
# Contact: Stefano Mosconi <stefano.mosconi@nokia.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA


# IN BRIEF:
# A simple hook script for the "post-receive" event that will launch a pmo-commit
# for each commit in the push.
#
# The "post-receive" script is run after receive-pack has accepted a pack
# and the repository has been updated.  It is passed arguments in through
# stdin in the form
#  <oldrev> <newrev> <refname>
# For example:
#  aa453216d1b3e49e7f6f98441fa56946ddcd6a20 68f7abf4e6f922807889f52bc043ecd31b79f814 refs/heads/master
#
# see contrib/hooks/ for an sample, or uncomment the next line and
# rename the file to "post-receive".

#. /usr/share/doc/git-core/contrib/hooks/post-receive-email

import logging
from optparse import OptionParser
from commands import getoutput
from random import randint
from os import getcwd, path
from minideblib import DpkgChangelog
import re
import sys
from vcscommit import VCStoBugzilla
from ConfigParser import ConfigParser

class CommitHook():
    """
    Class representing a commit hook
    """

    def __init__(self):
        """
        Initializes several variables
        """
        self.logger = logging.getLogger('post-receive')
        log_handler = logging.FileHandler('/var/log/vcs-post-receive/post-receive.log')
        formatter = logging.Formatter('%(asctime)s %(name)s (pid: %(process)d): [%(levelname)s] %(message)s')
        log_handler.setFormatter(formatter)
        self.logger.addHandler(log_handler)
        self.logger.setLevel(logging.DEBUG)
    
        self.chglog_end = re.compile('(.*\\n -- [A-Za-z].* <.*@.*\..*> .*\\n)')
        self.chglog = re.compile(r'.*debian/changelog')
        class dummy:
            pass
        self.vcsopts = dummy
        self.supported_vcs = ['hg','git','svn']
        self.parse_config()

    def parse_config(self):
        """
        Parses the config file
        """
        cfg = ConfigParser()
        cfg.read('/etc/vcs-post-receive/post-receive.cfg')
        defaults = cfg.defaults()
        self.bugzilla_url = defaults['bugzilla_url']
        self.rest_uri = defaults['rest_uri']
        self.netrc = defaults['netrc']
        self.vcsopts.proxy = defaults['proxy']
        self.vcs_conf = {}
        for vcs in self.supported_vcs:
           self.__dict__[vcs] = {}
           self.__dict__[vcs]['vcsurl'] = cfg.get(vcs, 'vcsurl')
           self.__dict__[vcs]['rootdir'] = cfg.get(vcs, 'rootdir')



    def parse_opts(self, args):
        """
        Parses command line options

        :param args: Commandline arguments
        :type args: sys.argv()
        """
        parser = OptionParser(usage='%prog [options]')
        parser.add_option('--tm', dest='tm', action="store_true", default=False, help='Set target milestone when closing')
        parser.add_option('-m', '--masteronly',  action="store_true", default=False, help='Restrict to master branch only')
        parser.add_option('--commentonly',  action="store_true", default=False, help='Comment only, don\'t resolve the bug')
        parser.add_option('-b', '--branch', type='string', action='store', dest='branch', help='Restrict to specified brances only')
        parser.add_option('--hg', dest='hg', metavar='HGNODE', action='store', type='string', help='Call for mercurial node')
        parser.add_option('--svn', dest='svn', metavar='REV_NUM', action='store', type='string', default=False, help='Call for svn repository with rev number')
        parser.add_option('--svnpath', dest='svnpath', metavar='SVN_PATH', action='store', type='string', default=False, help='svn repository path')


        (self.opts, _) = parser.parse_args(args)

        if (self.opts.branch and self.opts.masteronly):
            print >> sys.stderr, "Conflict in --branch and --masteronly"
            sys.exit(1)





    def check_opts(self):
        """
        Checks the options that were passed and configures the environment
        accordingly
        """
        if self.opts.hg:
            self.output = getoutput('hg log -v -r %s' % (self.opts.hg))
            self.rootdir = self.hg['rootdir']
            branch = getoutput('hg identify -b -r %s' % (self.opts.hg))
            self.commit = re.compile(r'changeset:\s*(.*)')
            self.author = re.compile(r'user:\s*(.*) <.*>')
            self.changed = re.compile(r'files:\s*(.*)')
            self.date = re.compile(r'date:.*')
            self.tag = re.compile(r'tag:.*')
            self.ignore = re.compile(r'(^Not trusting.*|description:.*)')
            self.get_changelog = 'hg cat -r %s %s'
            self.vcsopts.vcsurl = self.hg['vcsurl']
            self.vcsopts.vcstype = 'hg'
            self.logger.debug('hgnode: %s, ref: %s' % (self.opts.hg, branch))
            
        elif self.opts.svn:
            self.rootdir = self.svn['rootdir']
            self.vcsopts.vcsurl = self.svn['vcsurl']
            self.vcsopts.vcstype = 'svn'
            self.repository = self.opts.svnpath
            self.commit = self.opts.svn
            self.message = getoutput('/usr/bin/svnlook log -r %s %s' % (self.commit, self.repository))
            self.author = getoutput('/usr/bin/svnlook author -r %s %s' % (self.commit, self.repository))
            self.get_changelog = '/usr/bin/svnlook cat %s %s -r %s'
            self.files = getoutput('svnlook changed -r %s %s' % (self.commit, self.repository)).split('\n')
            self.logger.debug('Revision %s, repository %s, cwd %s\n' % (self.commit, self.repository, getcwd()))

        else:
            for line in sys.stdin:
                (oldrev, newrev, branch) = line.split()
            self.rootdir = self.git['rootdir']
            self.output = getoutput('git whatchanged %s..%s --reverse' % (oldrev, newrev))
            self.commit = re.compile(r'commit (.*)')
            self.author = re.compile(r'Author: (.*) <.*>')
            self.changed = re.compile(r'^:(.*)')
            self.date = re.compile(r'Date: .*')
            self.tag = self.ignore = re.compile(r'asndast125973126n2et,kapog8-sdf8024n561l3o6i0dwqysndflisdjrf971236')
            self.get_changelog = 'git cat-file blob %s'
            self.vcsopts.vcsurl = self.git['vcsurl']
            self.vcsopts.vcstype = 'git'
            self.logger.debug('Oldrev: %s, Newrev: %s. ref: %s' % (oldrev, newrev, branch))

        if not self.opts.svn:
            self.repository = getcwd().replace(self.rootdir, '').lstrip('/')


        if self.opts.masteronly:
            if self.opts.hg:
                if not branch == 'default':
                    sys.exit(0)
            else:
                if not branch == 'refs/heads/master':
                    sys.exit(0)


        if self.opts.branch:
            list_of_branches = self.opts.branch.split(',')
            if self.opts.hg:
                if not branch in list_of_branches:
                    sys.exit(0)
            else:
                if not branch.split('/')[2] in list_of_branches:
                    sys.exit(0)



    def scan_commits(self):
        """
        Does the real scan of the commits.

        It goes inside the repository and tries to find a debian/changelog with 
        Fixes: NB#.... string.

        If it doesn't and the commit message contains that kind of string it passes
        that to vcscommit object as a comment to bugzilla
        """
        commits = {}
        commitsinorder = []
        c = None

        if not self.opts.svn:
            for line in self.output.split('\n'):
                commits.setdefault(c, {})
                if self.commit.match(line):
                    c = self.commit.findall(line)[0]
                    commits[c] = {}
                    # Just to process the commits in order later
                    commitsinorder.append(c)
                elif self.author.match(line):
                    a = self.author.findall(line)[0]
                    commits[c]['author'] = a
                elif self.changed.match(line):
                    ch = self.changed.findall(line)[0]
                    if not commits[c].has_key('files'):
                        commits[c]['files'] = []
                    if self.opts.hg:
                    # files are in the same line?
                        commits[c]['files'].extend(ch.split())
                    else:
                        # [3] is the sha of the new blob, [5] is the name of the file
                        commits[c]['files'].append(ch.split()[3]+' '+ch.split()[5])
                elif not self.date.match(line) and not self.tag.match(line) and not self.ignore.match(line):
                    if not commits[c].has_key('msg'):
                        commits[c]['msg'] = line
                    else:
                        commits[c]['msg'] += '\n'+line
        else:
        # svn doesn't have multiple commits so not much job to do
            commits[self.commit] = {
            'msg': message,
            'files': [f.split()[1] for f in files if f],
            'author': self.author
            }
            commitsinorder = [self.commit]

            

        # Clear out the possibility a 'None' key was created in the case a message line
        # was assumed when in fact it was just bad input (weird but somehow happens -- see
        # BZ ticket #206719)
        commits.pop(None, None)

        for a_commit in commitsinorder:
        #look in all the commits
            for a_file in commits[a_commit]['files']:
            # check all the self.changed files in that commit
                if self.chglog.match(a_file):
                # if changelog is there get the message out of it
                # couldn't reduce the thing to one call only...
                    if self.opts.hg:
                        self.chglog_content = getoutput(self.get_changelog % (a_commit.split(':')[0], a_file))
                    elif self.opts.svn:
                        self.chglog_content = getoutput(self.get_changelog % (self.repository, a_file, a_commit))
                    else:
                        self.chglog_content = getoutput(self.get_changelog % a_file.split()[0].strip('.'))
                    # splitting all the changelog entries in a zipped way
                    # and getting the last changelog entry
                    spl = self.chglog_end.split(self.chglog_content)
                    if len(spl) == 1:
                        line = spl[0]
                    else:
                        line = map(lambda x: spl[x]+spl[x+1], range(0,len(spl)-1,2))[0].strip('\n')
                    print 'Found changelog entry:\n%s' % line
                    # adding it to the chglog
                    if not commits[a_commit].has_key('chglog'):
                        commits[a_commit]['chglog'] = line
                    else:
                        commits[a_commit]['chglog'] += '\n'+line
            # If we have the changelog, search for the Fixe* there
            # Otherwise search in the commit message
            if commits[a_commit].has_key('chglog'):
                foundit = commits[a_commit]['chglog'].find('Fixe')
                self.vcsopts.chglog = '%s' % commits[a_commit]['chglog']
            else:
                foundit = commits[a_commit]['msg'].find('Fixe')
                self.vcsopts.chglog = ''

            if foundit != -1:
                print 'Starting bugzilla hook for commit %s' % a_commit
                if self.opts.svn:
                    self.repository = self.repository.replace(self.rootdir, '').lstrip('/')
                self.vcsopts.vcsurl = path.join(self.vcsopts.vcsurl, self.repository)
                self.vcsopts.rev = a_commit
                self.vcsopts.user = commits[a_commit]['author']
                self.vcsopts.msg = commits[a_commit]['msg']
                self.vcsopts.tm = self.opts.tm
                self.vcsopts.commentonly = self.opts.commentonly
                self.vcsopts.netrc = self.netrc
                self.vcsopts.bugzilla = self.bugzilla_url
                self.vcsopts.rest_uri = self.rest_uri
                VCStoBugzilla(self.vcsopts).run()

    def main(self, args):
        """
        Main routine
        """
        self.parse_opts(args)
        self.check_opts()
        self.scan_commits()
        



if __name__ == '__main__':
    CommitHook().main(sys.argv)
