extensions="acpid all-modules boot-wait console cpuinfo disks dtbpatch early-telnet eudev misc nvme-cache powersched tcrp-diag wol"


for extension in $extensions
do
	echo -n "Fixing $extension : "
	cd ../$extension && jq . rpext-index.json >a && mv a rpext-index.json && jq . rpext-index.json |wc -l && cd ../maintenance
	
done
