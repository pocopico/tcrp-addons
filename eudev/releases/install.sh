#!/usr/bin/env ash

# DSM version
MajorVersion=`/bin/get_key_value /etc.defaults/VERSION majorversion`
MinorVersion=`/bin/get_key_value /etc.defaults/VERSION minorversion`
ModuleUnique=`/bin/get_key_value /etc.defaults/VERSION unique` # Avoid confusion with global variables

echo "MajorVersion:${MajorVersion} MinorVersion:${MinorVersion}"


### USUALLY SCEMD is the last process run in init, so when scemd is running we are most
# probably certain that system has finish init process
#


if [ `mount | grep tmpRoot | wc -l` -gt 0 ] ; then
HASBOOTED="yes"
echo -n "System passed junior"
else
echo -n "System is booting"
HASBOOTED="no"
fi

if [ "$HASBOOTED" = "no" ]; then

  echo "Starting eudev daemon - modules"
  cd /
  if [ "${MajorVersion}" -lt "7" ]; then # < 7
  tar xfz /exts/eudev/eudev-6.2.tgz -C /
  else
    if [ "${MinorVersion}" -lt "2" ]; then # < 2
  tar xfz /exts/eudev/eudev-7.1.tgz -C /
    else
  tar xfz /exts/eudev/eudev-7.2.tgz -C /
    fi
  fi
  ln -s /lib/libkmod.so.2.4.0 /lib/libkmod.so.2
  ln -s /usr/bin/udevadm /usr/sbin/udevadm
  [ -e /proc/sys/kernel/hotplug ] && printf '\000\000\000\000' > /proc/sys/kernel/hotplug
  /sbin/udevd -d || { echo "FAIL"; exit 1; }
  echo "Triggering add events to udev"
  udevadm trigger --type=subsystems --action=add
  udevadm trigger --type=devices --action=add
  udevadm trigger --type=devices --action=change
  udevadm settle --timeout=30 || echo "udevadm settle failed"
  # Give more time
  sleep 10
  # Remove from memory to not conflict with RAID mount scripts
  /usr/bin/killall udevd
elif [ "$HASBOOTED" = "yes" ]; then
  echo "eudev - late"
  # Copy rules
  cp -vf /etc/udev/rules.d/* /tmpRoot/usr/lib/udev/rules.d/
  DEST="/tmpRoot/lib/systemd/system/udevrules.service"

  echo "[Unit]"                                                                  >${DEST}
  echo "Description=Reload udev rules"                                          >>${DEST}
  echo                                                                          >>${DEST}
  echo "[Service]"                                                              >>${DEST}
  echo "Type=oneshot"                                                           >>${DEST}
  echo "RemainAfterExit=true"                                                   >>${DEST}
  echo "ExecStart=/usr/bin/udevadm hwdb --update"                               >>${DEST}
  echo "ExecStart=/usr/bin/udevadm control --reload-rules"                      >>${DEST}
  echo                                                                          >>${DEST}
  echo "[Install]"                                                              >>${DEST}
  echo "WantedBy=multi-user.target"                                             >>${DEST}

  mkdir -p /tmpRoot/etc/systemd/system/multi-user.target.wants
  ln -sf /lib/systemd/system/udevrules.service /tmpRoot/lib/systemd/system/multi-user.target.wants/udevrules.service
fi

