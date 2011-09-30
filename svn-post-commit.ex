REPOS="$1"
REV="$2"

/usr/bin/python /usr/bin/post-receive --svn $REV --svnpath $REPOS
