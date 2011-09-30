#!/bin/sh

data=$(cat)
echo $data
/usr/bin/python /usr/bin/post-receive << EOF
$data
EOF
