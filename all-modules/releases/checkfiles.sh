#!/bin/bash

# Check and update files and sha256sums for all-modules

#echo "Getting latest chksum.log"
#curl --insecure -L https://github.com/pocopico/redpill-modules/releases/latest/download/chksum.log

command="$1"
platform="$2"

if [ -z "$platform" ] ; then
platforms="apollolake broadwell broadwellnk bromolow denverton epyc7002 geminilake r1000 v1000"
else
platforms="$platform"
fi

for platform in $platforms; do
    echo "Checking $platform"

    while read url sha; do

        file=$(echo $url | awk -F\/ '{print $9}')

        curl --insecure -sL "$url" -o $file
        sha256=$(sha256sum $file | awk '{print $1}')
        rm $file
        if [ "$sha" == "$sha256" ]; then
            echo "File $file -> OK"
        else
	    fixes="1"
            echo "ERROR, File: $file LOCALSHA:$sha REMOTESHA:$sha256"
            if [ "$command" == "fix" ]; then
                echo "Fixing local values, $file"
                sed -i "s/$sha/$sha256/g" ${platform}.json
            fi
        fi

    done <<<$(jq -re '.files[] | .url , .sha256' ${platform}.json | paste -d " " - -)
done

[ "$command" = "fix" ] && [ "$fixes" = "1" ] && git status && git commit -a -m "Fixing checksums" &&  git push 
