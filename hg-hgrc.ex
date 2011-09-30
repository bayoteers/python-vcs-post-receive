# Add this to your hgrc in your hg repo

[hooks]
incoming.bugzilla = /usr/bin/post-receive --hg $HG_NODE

