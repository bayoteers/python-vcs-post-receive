#!/bin/sh

data=$(cat)
echo $data
/usr/bin/python /usr/local/bin/post-receive << EOF
$data
EOF
/usr/share/repo_manager/git/hooks/post-receive-email << EOF
$data
EOF
