#!/bin/bash

function header() {
	cat <<EOF
{
  "id": "all-modules",
  "url": "https://raw.githubusercontent.com/pocopico/tcrp-addons/main/all-modules/rpext-index.json",
  "info": {
    "author_url": "https://github.com/pocopico",
    "description": "Adds All modules Support",
    "help_url": "<todo>",
    "name": "all-modules",
    "packer_url": "https://github.com/pocopico/tcrp-addons/tree/main/all-modules"
  },
  "releases": {
EOF

}

function build_config() {

	model="$1"
	version="$2"
	revision="$(echo $2 | cut -d'-' -f2)"
	platforms $model
	cat <<EOF
 "${model}_${revision}":  "https://raw.githubusercontent.com/pocopico/tcrp-addons/main/acpid/recipes/universal.json",
EOF
}

function footer() {
	cat <<EOF
     "zendofmodel": "endofurls"
  }
}
EOF
}

function platforms() {

	case $1 in

	ds1019p | ds918p)
		platform="apollolake"
		;;
	ds1520p | ds920p | dva1622)
		platform="geminilake"
		;;
	ds1621p | ds2422p | fs2500)
		platform="v1000"
		;;
	ds1621xsp | ds3622xsp | rs4021xsp)
		platform="broadwellnk"
		;;
	ds3615xs | rs3413xsp)
		platform="bromolow"
		;;
	ds3617xs | rs3618xs)
		platform="broadwell"
		;;
	ds723p | ds923p)
		platform="r1000"
		;;
	dva3219 | dva3221)
		platform="denverton"
		;;
	fs6400)
		platform="purley"
		;;
	sa6400)
		platform="epyc7002"
		;;
	esac
}

header

for model in $(cat supportedmodels); do
	for version in $(cat versions); do
		build_config $model $version
	done
done

footer
