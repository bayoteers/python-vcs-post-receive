__author__="Stefano Mosconi <stefano.mosconi@nokia.com>"
__date__ ="$Sep 7, 2011 10:32:47 PM$"

from setuptools import setup,find_packages

def debpkgver(changelog = "debian/changelog"):
    return open(changelog).readline().split(' ')[1][1:-1]

setup (
  name = 'python-vcs-post-receive',
  version = debpkgver(),
  packages = find_packages(),

  # Fill in these to make your Egg ready for upload to
  # PyPI
  author = 'Stefano Mosconi',
  author_email = 'stefano.mosconi@nokia.com',

  description = 'Simple vcs-post-receive script that uses vcs-commit to comment on bugzilla',
  license = 'GPL',
  long_description= '''
  Parses the commits contained in a push and fires up vcs-commit script that then comments
  on bugzilla bugs (the ones specicified with the syntax Fixes: #BUGN)
  ''',
  py_modules=["post_receive"],

  # could also include long_description, download_url, classifiers, etc.

  classifiers=[
      "Development Status :: 4 - Beta",
      "Operating System :: Unix",
      "License :: OSI Approved :: GNU General Public License (GPL)",
      "Intended Audience :: System Administrators",
      "Programming Language :: Python",
      "Topic :: Tools :: Bugzilla"
  ]
  
)
