#!/bin/sh
#
# install redpill tcrp modules
#

function getvars() {
TARGET_PLATFORM="$(uname -u | cut -d '_' -f2)"
LINUX_VER="$(uname -r | cut -d '+' -f1)"
}

function prepare_eudev() {
echo "Copying kmod,tar to /bin/"
/bin/cp -v kmod  /bin/       ; chmod 700 /bin/kmod
#/bin/cp -v tar  /bin/        ; chmod 700 /bin/tar
echo "link depmod to kmod"
ln -s /bin/kmod /usr/sbin/depmod
echo "Extracting modules"
tar xfz /exts/all-modules/${TARGET_PLATFORM}-${LINUX_VER}.tgz -C /lib/modules/
mkdir /lib/firmware
echo "Extracting firmware"
tar xfz /exts/all-modules/firmware.tgz -C /lib/firmware/
/usr/sbin/depmod -a
}

function checkforsas() {

sasmods="mpt3sas hpsa mvsas"
for sasmodule in $sasmods
do
echo "Checking existense of $sasmodule"
for alias in `depmod -n 2>/dev/null |grep -i $sasmodule |grep pci|cut -d":" -f 2 | cut -c 6-9,15-18`
do
if [ `grep -i $alias /proc/bus/pci/devices |wc -l` -gt 0 ] ; then
echo "  => $sasmodule, device found, loading module" 
insmod /lib/modules/${sasmodule}.ko 
fi
done
done 

}


getvars
checkforsas
prepare_eudev
